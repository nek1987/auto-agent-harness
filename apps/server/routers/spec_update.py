"""
Spec Update Router
==================

Endpoints for updating an existing app_spec based on a large requirements doc.
"""

import json
import logging
import re
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.process_manager import check_agent_lock
from ..services.spec_update_service import (
    SpecUpdateAnalyzer,
    add_spec_version_to_manifest,
    build_analysis_id,
    load_analysis,
    similarity,
    store_analysis,
    write_spec_version,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spec/update", tags=["spec-update"])


class SpecUpdateAnalyzeRequest(BaseModel):
    project_name: str = Field(..., description="Project name")
    input_text: str = Field(..., description="Requirements text (md/txt)")
    mode: Literal["merge", "rebuild"] = "merge"
    analysis_model: Optional[str] = Field(default=None, description="Claude model override")


class FeatureCandidate(BaseModel):
    feature_key: str
    name: str
    description: str
    steps: list[str]
    category: str
    source_anchor: str


class MatchCandidate(BaseModel):
    feature_id: int
    name: str
    confidence: float
    change_type: Literal["cosmetic", "logic"]


class MatchGroup(BaseModel):
    feature_key: str
    suggested_id: Optional[int]
    candidates: list[MatchCandidate]


class SpecUpdateAnalyzeResponse(BaseModel):
    analysis_id: str
    proposed_spec: str
    diff: dict
    coverage: list[dict]
    coverage_complete: bool
    feature_candidates: list[FeatureCandidate]
    match_candidates: list[MatchGroup]
    conflicts: list[dict]


class MappingDecision(BaseModel):
    feature_key: str
    action: Literal["update", "create", "skip"] = "create"
    existing_feature_id: Optional[int] = None
    change_type: Literal["cosmetic", "logic"] = "logic"


class SpecUpdateApplyRequest(BaseModel):
    project_name: str
    analysis_id: str
    mapping: list[MappingDecision]
    notes: Optional[str] = None


class SpecUpdateApplyResponse(BaseModel):
    version_id: str
    updated: int
    created: int
    skipped: int
    needs_review: int


# Lazy imports to avoid circular dependencies
_get_project_path = None
_import_spec_content = None
_get_app_spec = None
_create_database = None
_Feature = None


def _init_imports() -> None:
    global _get_project_path, _import_spec_content, _get_app_spec, _create_database, _Feature
    if _get_project_path is None:
        import sys
        root = Path(__file__).parent.parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from registry import get_project_path
        from prompts import import_spec_content, get_app_spec
        from api.database import Feature, create_database

        _get_project_path = get_project_path
        _import_spec_content = import_spec_content
        _get_app_spec = get_app_spec
        _create_database = create_database
        _Feature = Feature


def _get_db_session(project_dir: Path):
    create_database, Feature = _create_database, _Feature
    _, SessionLocal = create_database(project_dir)
    return SessionLocal(), Feature


def _infer_category(tags: list[str], source_anchor: str) -> str:
    anchor = (source_anchor or "").lower()
    tag_text = " ".join(tags).lower()
    combined = f"{anchor} {tag_text}"
    if "ui" in combined or "frontend" in combined:
        return "frontend_features"
    if "api" in combined or "backend" in combined:
        return "backend_features"
    if "database" in combined or "db" in combined:
        return "database"
    return "workflow"


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return value.strip("-") or "feature"


def _build_feature_candidates(requirements: list[dict]) -> list[FeatureCandidate]:
    candidates: list[FeatureCandidate] = []
    for idx, req in enumerate(requirements):
        name = str(req.get("title") or "Untitled feature").strip()
        description = str(req.get("description") or "").strip() or name
        steps = [str(step).strip() for step in req.get("acceptance") or [] if str(step).strip()]
        tags = [str(tag).strip() for tag in req.get("tags") or [] if str(tag).strip()]
        source_anchor = str(req.get("source_anchor") or "")
        feature_key = f"{_slugify(name)}-{idx}"
        category = _infer_category(tags, source_anchor)
        candidates.append(
            FeatureCandidate(
                feature_key=feature_key,
                name=name,
                description=description,
                steps=steps,
                category=category,
                source_anchor=source_anchor,
            )
        )
    return candidates


def _build_match_candidates(feature_candidates: list[FeatureCandidate], existing_features: list) -> list[MatchGroup]:
    match_groups: list[MatchGroup] = []
    for candidate in feature_candidates:
        scored: list[MatchCandidate] = []
        for feature in existing_features:
            text_a = f"{candidate.name} {candidate.description}"
            text_b = f"{feature.name} {feature.description}"
            score = similarity(text_a, text_b)
            if score < 0.2:
                continue
            change_type = "cosmetic" if score >= 0.92 else "logic"
            scored.append(
                MatchCandidate(
                    feature_id=feature.id,
                    name=feature.name,
                    confidence=round(score, 3),
                    change_type=change_type,
                )
            )
        scored.sort(key=lambda item: item.confidence, reverse=True)
        top = scored[:3]
        suggested = top[0].feature_id if top else None
        match_groups.append(
            MatchGroup(
                feature_key=candidate.feature_key,
                suggested_id=suggested,
                candidates=top,
            )
        )
    return match_groups


@router.post("/analyze", response_model=SpecUpdateAnalyzeResponse)
async def analyze_spec_update(request: SpecUpdateAnalyzeRequest):
    _init_imports()

    project_dir = _get_project_path(request.project_name)
    if not project_dir or not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    is_running, _ = check_agent_lock(project_dir)
    if is_running:
        raise HTTPException(status_code=409, detail="Cannot update spec while agent is running. Stop the agent first.")

    existing_spec = ""
    try:
        existing_spec = _get_app_spec(project_dir)
    except Exception:
        existing_spec = ""

    analyzer = SpecUpdateAnalyzer(model=request.analysis_model or "claude-sonnet-4-20250514")
    analysis = await analyzer.analyze(request.input_text, existing_spec)

    feature_candidates = _build_feature_candidates(analysis["requirements"])

    existing_features: list = []
    db_file = project_dir / "features.db"
    if db_file.exists():
        session, Feature = _get_db_session(project_dir)
        try:
            existing_features = session.query(Feature).order_by(Feature.priority).all()
        finally:
            session.close()

    match_candidates = _build_match_candidates(feature_candidates, existing_features)

    analysis_id = build_analysis_id()
    analysis_payload = {
        **analysis,
        "feature_candidates": [candidate.model_dump() for candidate in feature_candidates],
        "match_candidates": [group.model_dump() for group in match_candidates],
    }
    stored = store_analysis(project_dir, analysis_id, analysis_payload, request.input_text)
    analysis_payload["input_file"] = stored.get("input_file")
    analysis_payload["analysis_file"] = stored.get("analysis_file")

    coverage_complete = all(item["requirements"] > 0 for item in analysis["coverage"]) if analysis["coverage"] else True

    return SpecUpdateAnalyzeResponse(
        analysis_id=analysis_id,
        proposed_spec=analysis["proposed_spec"],
        diff=analysis["diff"],
        coverage=analysis["coverage"],
        coverage_complete=coverage_complete,
        feature_candidates=feature_candidates,
        match_candidates=match_candidates,
        conflicts=[],
    )


@router.post("/apply", response_model=SpecUpdateApplyResponse)
async def apply_spec_update(request: SpecUpdateApplyRequest):
    _init_imports()

    project_dir = _get_project_path(request.project_name)
    if not project_dir or not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    is_running, _ = check_agent_lock(project_dir)
    if is_running:
        raise HTTPException(status_code=409, detail="Cannot update spec while agent is running. Stop the agent first.")

    analysis = load_analysis(project_dir, request.analysis_id)
    proposed_spec = analysis.get("proposed_spec")
    if not proposed_spec:
        raise HTTPException(status_code=422, detail="Analysis data missing proposed spec")

    # Update app_spec.txt
    try:
        _import_spec_content(project_dir, proposed_spec, validate=True, spec_name="main")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Spec validation failed: {exc}")

    version_entry = write_spec_version(project_dir, request.analysis_id, proposed_spec, analysis.get("diff", {}), request.notes)
    version_entry["input_file"] = analysis.get("input_file") if isinstance(analysis.get("input_file"), str) else None
    add_spec_version_to_manifest(project_dir, version_entry)

    # Save mapping decisions for traceability
    updates_dir = project_dir / "prompts" / "spec_updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    mapping_file = updates_dir / f"mapping_{request.analysis_id}.json"
    mapping_file.write_text(
        json.dumps([decision.model_dump() for decision in request.mapping], indent=2),
        encoding="utf-8",
    )

    # Apply feature updates
    session, Feature = _get_db_session(project_dir)
    existing_features = session.query(Feature).order_by(Feature.priority).all()
    existing_by_id = {feature.id: feature for feature in existing_features}

    feature_candidates = analysis.get("feature_candidates", [])
    decisions = {decision.feature_key: decision for decision in request.mapping}

    updated = 0
    created = 0
    skipped = 0
    needs_review = 0

    max_priority = max([feature.priority for feature in existing_features], default=0)

    try:
        for candidate in feature_candidates:
            feature_key = candidate.get("feature_key")
            decision = decisions.get(feature_key)
            if not decision or decision.action == "skip":
                skipped += 1
                continue

            if decision.action == "update" and decision.existing_feature_id:
                target = existing_by_id.get(decision.existing_feature_id)
                if not target:
                    skipped += 1
                    continue
                target.name = candidate.get("name")
                target.description = candidate.get("description")
                target.steps = candidate.get("steps") or []
                if decision.change_type == "logic":
                    target.passes = False
                    target.in_progress = False
                    target.review_status = "needs_review"
                    needs_review += 1
                else:
                    target.review_status = None
                updated += 1
                continue

            if decision.action == "create":
                max_priority += 1
                new_feature = Feature(
                    priority=max_priority,
                    category=candidate.get("category") or "workflow",
                    name=candidate.get("name"),
                    description=candidate.get("description"),
                    steps=candidate.get("steps") or [],
                    passes=False,
                    in_progress=False,
                    review_status=None,
                )
                session.add(new_feature)
                created += 1

        session.commit()
    finally:
        session.close()

    return SpecUpdateApplyResponse(
        version_id=request.analysis_id,
        updated=updated,
        created=created,
        skipped=skipped,
        needs_review=needs_review,
    )
