"""
Features Router
===============

API endpoints for feature/test case management.
"""

import logging
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..schemas import (
    BugCreate,
    FeatureCreate,
    FeatureListResponse,
    FeatureResponse,
)
from ..services.complexity_analyzer import get_complexity_analyzer

# Lazy imports to avoid circular dependencies
_create_database = None
_Feature = None

logger = logging.getLogger(__name__)


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def _get_db_classes():
    """Lazy import of database classes."""
    global _create_database, _Feature
    if _create_database is None:
        import sys
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from api.database import Feature, create_database
        _create_database = create_database
        _Feature = Feature
    return _create_database, _Feature


router = APIRouter(prefix="/api/projects/{project_name}/features", tags=["features"])


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name"
        )
    return name


@contextmanager
def get_db_session(project_dir: Path):
    """
    Context manager for database sessions.
    Ensures session is always closed, even on exceptions.
    """
    create_database, _ = _get_db_classes()
    _, SessionLocal = create_database(project_dir)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def feature_to_response(f) -> FeatureResponse:
    """Convert a Feature model to a FeatureResponse."""
    return FeatureResponse(
        id=f.id,
        priority=f.priority,
        category=f.category,
        name=f.name,
        description=f.description,
        steps=f.steps if isinstance(f.steps, list) else [],
        passes=f.passes,
        in_progress=f.in_progress,
        item_type=getattr(f, 'item_type', 'feature') or 'feature',
        parent_bug_id=getattr(f, 'parent_bug_id', None),
        bug_status=getattr(f, 'bug_status', None),
        assigned_skills=getattr(f, 'assigned_skills', None),
    )


@router.get("", response_model=FeatureListResponse)
async def list_features(project_name: str):
    """
    List all features for a project organized by status.

    Returns features in three lists:
    - pending: passes=False, not currently being worked on
    - in_progress: features currently being worked on (tracked via agent output)
    - done: passes=True
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db_file = project_dir / "features.db"
    if not db_file.exists():
        return FeatureListResponse(pending=[], in_progress=[], done=[])

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            all_features = session.query(Feature).order_by(Feature.priority).all()

            pending = []
            in_progress = []
            done = []

            for f in all_features:
                feature_response = feature_to_response(f)
                if f.passes:
                    done.append(feature_response)
                elif f.in_progress:
                    in_progress.append(feature_response)
                else:
                    pending.append(feature_response)

            return FeatureListResponse(
                pending=pending,
                in_progress=in_progress,
                done=done,
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error in list_features")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.post("/analyze-complexity")
async def analyze_feature_complexity(project_name: str, feature: FeatureCreate):
    """
    Analyze feature complexity and return decomposition recommendation.

    This endpoint should be called BEFORE create_feature to determine
    if the feature should be decomposed into subtasks.

    Returns:
        - score: Complexity score (1-10)
        - level: "simple", "medium", or "complex"
        - shouldDecompose: Whether decomposition is recommended
        - suggestedApproach: "direct", "recommend_decompose", or "require_decompose"
        - reasons: List of factors contributing to the complexity score
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    analyzer = get_complexity_analyzer()
    analysis = analyzer.analyze(
        name=feature.name,
        description=feature.description,
        steps=feature.steps or [],
        category=feature.category,
    )

    return analysis.to_dict()


@router.post("/split-preview")
async def preview_feature_split(project_name: str, feature: FeatureCreate):
    """
    Preview how a feature would be split based on step analysis.

    This is a lightweight alternative to AI-based decomposition
    for features with many steps that follow clear patterns.
    """
    project_name = validate_project_name(project_name)

    # Import feature_splitter from lib
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from lib.feature_splitter import FeatureSplitter

    splitter = FeatureSplitter()

    # Get recommendation first
    feature_dict = {
        "name": feature.name,
        "category": feature.category,
        "description": feature.description,
        "steps": feature.steps or [],
    }

    recommendation = splitter.get_split_recommendation(feature_dict)

    if not recommendation["should_split"]:
        return {
            "shouldSplit": False,
            "complexity": recommendation["complexity"],
            "reason": recommendation["reason"],
            "subFeatures": [],
        }

    # Preview the split
    result = splitter.analyze_and_split([feature_dict], auto_split=True)

    return {
        "shouldSplit": True,
        "complexity": recommendation["complexity"],
        "reason": recommendation["reason"],
        "originalStepCount": len(feature.steps) if feature.steps else 0,
        "subFeatureCount": len(result.features),
        "subFeatures": result.features,
    }


@router.post("/create-bulk")
async def create_features_bulk(project_name: str, features: list[FeatureCreate]):
    """
    Create multiple features at once (for decomposed tasks).

    This endpoint skips complexity checks since the features
    are assumed to be already decomposed.
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            # Get starting priority
            max_priority_feature = session.query(Feature).order_by(Feature.priority.desc()).first()
            next_priority = (max_priority_feature.priority + 1) if max_priority_feature else 1

            created = []
            for i, feature_data in enumerate(features):
                db_feature = Feature(
                    priority=next_priority + i,
                    category=feature_data.category,
                    name=feature_data.name,
                    description=feature_data.description,
                    steps=feature_data.steps or [],
                    passes=False,
                    item_type=feature_data.item_type,
                    assigned_skills=feature_data.assigned_skills,
                )
                session.add(db_feature)
                created.append(db_feature)

            session.commit()

            # Refresh all to get IDs
            for f in created:
                session.refresh(f)

            return {
                "success": True,
                "created": len(created),
                "features": [feature_to_response(f) for f in created],
            }
    except Exception:
        logger.exception("Failed to create features in bulk")
        raise HTTPException(status_code=500, detail="Failed to create features")


@router.post("", response_model=FeatureResponse)
async def create_feature(
    project_name: str,
    feature: FeatureCreate,
    skip_complexity_check: bool = Query(default=False, description="Skip complexity validation"),
):
    """
    Create a new feature/test case or bug report manually.

    By default, complex features will return a 422 error with decomposition recommendation.
    Set skip_complexity_check=True to bypass this (for pre-decomposed tasks or known simple features).
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Complexity gate: check if feature needs decomposition
    # Skip for: bugs, features with assigned skills (already decomposed), explicit skip
    is_bug = feature.item_type == "bug"
    has_assigned_skills = feature.assigned_skills and len(feature.assigned_skills) > 0

    if not skip_complexity_check and not is_bug and not has_assigned_skills:
        analyzer = get_complexity_analyzer()
        analysis = analyzer.analyze(
            name=feature.name,
            description=feature.description,
            steps=feature.steps or [],
            category=feature.category,
        )

        if analysis.suggested_approach == "require_decompose":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "complexity_requires_decomposition",
                    "message": f"Feature complexity score: {analysis.score}/10. Decomposition required.",
                    "analysis": analysis.to_dict(),
                    "action": "Please use Skills Analysis to decompose this feature into smaller tasks.",
                }
            )

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:

            # Bugs always get priority 0 (highest), features get next available
            if is_bug:
                priority = 0
            elif feature.priority is None:
                max_priority = session.query(Feature).order_by(Feature.priority.desc()).first()
                priority = (max_priority.priority + 1) if max_priority else 1
            else:
                priority = feature.priority

            # Create new feature or bug
            db_feature = Feature(
                priority=priority,
                category="bug" if is_bug else feature.category,
                name=feature.name,
                description=feature.description,
                steps=feature.steps,
                passes=False,
                item_type=feature.item_type,
                bug_status="open" if is_bug else None,
                assigned_skills=feature.assigned_skills if not is_bug else None,
            )

            session.add(db_feature)
            session.commit()
            session.refresh(db_feature)

            return feature_to_response(db_feature)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create feature")
        raise HTTPException(status_code=500, detail="Failed to create feature")


@router.post("/bug", response_model=FeatureResponse)
async def create_bug(project_name: str, bug: BugCreate):
    """Create a bug report with high priority. Agent will analyze and create fix features."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            # Bugs always have priority 0 (highest)
            db_bug = Feature(
                priority=0,
                category="bug",
                name=bug.name,
                description=bug.description,
                steps=bug.steps_to_reproduce if bug.steps_to_reproduce else ["Reproduce the bug"],
                passes=False,
                item_type="bug",
                bug_status="open",
            )

            session.add(db_bug)
            session.commit()
            session.refresh(db_bug)

            return feature_to_response(db_bug)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create bug")
        raise HTTPException(status_code=500, detail="Failed to create bug")


@router.get("/{feature_id}", response_model=FeatureResponse)
async def get_feature(project_name: str, feature_id: int):
    """Get details of a specific feature."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db_file = project_dir / "features.db"
    if not db_file.exists():
        raise HTTPException(status_code=404, detail="No features database found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            return feature_to_response(feature)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error in get_feature")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.delete("/{feature_id}")
async def delete_feature(project_name: str, feature_id: int):
    """Delete a feature."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            session.delete(feature)
            session.commit()

            return {"success": True, "message": f"Feature {feature_id} deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete feature")
        raise HTTPException(status_code=500, detail="Failed to delete feature")


@router.patch("/{feature_id}/skip")
async def skip_feature(project_name: str, feature_id: int):
    """
    Mark a feature as skipped by moving it to the end of the priority queue.

    This doesn't delete the feature but gives it a very high priority number
    so it will be processed last.
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            # Set priority to max + 1000 to push to end
            max_priority = session.query(Feature).order_by(Feature.priority.desc()).first()
            feature.priority = (max_priority.priority if max_priority else 0) + 1000

            session.commit()

            return {"success": True, "message": f"Feature {feature_id} moved to end of queue"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to skip feature")
        raise HTTPException(status_code=500, detail="Failed to skip feature")
