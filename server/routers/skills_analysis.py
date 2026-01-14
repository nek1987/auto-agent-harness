"""
Skills Analysis Router
======================

WebSocket and REST endpoints for skills-based feature analysis.
Provides skill selection, feature decomposition, and task generation.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..services.skills_catalog import (
    SkillMetadata,
    get_skills_catalog,
    reset_skills_catalog,
)
from ..services.skills_selector import (
    SkillsSelector,
    get_skills_selector,
)
from ..services.feature_decomposer import (
    FeatureDecomposer,
    create_decomposer,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills-analysis", tags=["skills-analysis"])


def _get_project_path(project_name: str) -> Optional[Path]:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def validate_project_name(name: str) -> bool:
    """Validate project name to prevent path traversal."""
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,50}$', name))


# ============================================================================
# Request/Response Schemas
# ============================================================================

class SkillSearchRequest(BaseModel):
    """Request to search skills."""
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)


class SkillInfo(BaseModel):
    """Skill information response."""
    name: str
    displayName: str
    description: str
    tags: list[str]
    capabilities: list[str]
    hasScripts: bool
    hasReferences: bool
    techStack: list[str] = Field(default_factory=list)


class CatalogSummary(BaseModel):
    """Catalog summary response."""
    totalSkills: int
    categories: list[str]
    categoryCounts: dict[str, int]
    technologies: list[str]


class FeatureAnalysisRequest(BaseModel):
    """Request for feature analysis."""
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    steps: list[str] = Field(default_factory=list)


# ============================================================================
# REST Endpoints - Catalog
# ============================================================================

@router.get("/catalog", response_model=CatalogSummary)
async def get_catalog_summary():
    """Get catalog summary with statistics."""
    catalog = get_skills_catalog()
    summary = catalog.get_catalog_summary()
    return CatalogSummary(**summary)


@router.get("/catalog/all", response_model=list[SkillInfo])
async def get_all_skills(limit: int = 100):
    """Get all skills in the catalog."""
    catalog = get_skills_catalog()
    skills = catalog.get_all_skills()[:limit]
    return [SkillInfo(
        name=s.name,
        displayName=s.display_name,
        description=s.description,
        tags=s.tags,
        capabilities=s.capabilities,
        hasScripts=s.has_scripts,
        hasReferences=s.has_references,
        techStack=s.tech_stack,
    ) for s in skills]


@router.get("/catalog/{skill_name}", response_model=SkillInfo)
async def get_skill_details(skill_name: str):
    """Get details for a specific skill."""
    catalog = get_skills_catalog()
    skill = catalog.get_skill(skill_name)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    return SkillInfo(
        name=skill.name,
        displayName=skill.display_name,
        description=skill.description,
        tags=skill.tags,
        capabilities=skill.capabilities,
        hasScripts=skill.has_scripts,
        hasReferences=skill.has_references,
        techStack=skill.tech_stack,
    )


@router.post("/search", response_model=list[SkillInfo])
async def search_skills(request: SkillSearchRequest):
    """Search skills by keywords, tags, or technologies."""
    catalog = get_skills_catalog()
    results = []

    if request.keywords:
        results.extend(catalog.search_by_keywords(request.keywords, limit=request.limit))

    if request.tags:
        tag_results = catalog.search_by_tags(request.tags)
        for skill in tag_results:
            if skill not in [r for r in results if r.name == skill.name]:
                results.append(skill)

    if request.technologies:
        tech_results = catalog.search_by_tech(request.technologies)
        for skill in tech_results:
            if skill not in [r for r in results if r.name == skill.name]:
                results.append(skill)

    # Dedupe and limit
    seen = set()
    unique_results = []
    for skill in results:
        if skill.name not in seen:
            seen.add(skill.name)
            unique_results.append(skill)

    return [SkillInfo(
        name=s.name,
        displayName=s.display_name,
        description=s.description,
        tags=s.tags,
        capabilities=s.capabilities,
        hasScripts=s.has_scripts,
        hasReferences=s.has_references,
        techStack=s.tech_stack,
    ) for s in unique_results[:request.limit]]


@router.get("/categories")
async def get_categories():
    """Get list of skill categories."""
    catalog = get_skills_catalog()
    index = catalog.get_index()
    return {
        "categories": list(index.by_tag.keys()),
        "counts": {tag: len(names) for tag, names in index.by_tag.items()},
    }


@router.post("/refresh")
async def refresh_catalog():
    """Refresh the skills catalog index."""
    reset_skills_catalog()
    catalog = get_skills_catalog()
    catalog.build_index(force=True)
    summary = catalog.get_catalog_summary()
    return {
        "success": True,
        "message": f"Refreshed catalog with {summary['totalSkills']} skills",
        **summary,
    }


# ============================================================================
# REST Endpoints - Selection
# ============================================================================

@router.post("/select")
async def select_skills_for_feature(request: FeatureAnalysisRequest):
    """Select skills for a feature (non-streaming)."""
    selector = get_skills_selector()

    result = selector.select_skills_for_feature(
        name=request.name,
        description=request.description,
        category=request.category,
        steps=request.steps,
    )

    return result.to_dict()


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{project_name}")
async def skills_analysis_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for skills-based feature analysis.

    Message protocol:

    Client -> Server:
    - {"type": "analyze", "feature": {...}} - Start analysis with feature data
    - {"type": "select_skills", "skill_ids": [...]} - Confirm skill selection
    - {"type": "decompose", "selected_skills": [...]} - Decompose with skills
    - {"type": "update_task", "task_id": "...", "updates": {...}} - Update task
    - {"type": "confirm", "tasks": [...]} - Confirm final tasks
    - {"type": "ping"} - Keep-alive ping

    Server -> Client:
    - {"type": "status", "content": "..."} - Status update
    - {"type": "skills_suggested", "selection": {...}} - Suggested skills
    - {"type": "task_generated", "task": {...}} - Generated task
    - {"type": "decomposition_complete", "result": {...}} - All tasks generated
    - {"type": "error", "content": "..."} - Error message
    - {"type": "pong"} - Keep-alive pong
    """
    if not validate_project_name(project_name):
        await websocket.close(code=4000, reason="Invalid project name")
        return

    # Look up project directory from registry
    project_dir = _get_project_path(project_name)
    if not project_dir:
        await websocket.close(code=4004, reason="Project not found in registry")
        return

    if not project_dir.exists():
        await websocket.close(code=4004, reason="Project directory not found")
        return

    await websocket.accept()

    decomposer: Optional[FeatureDecomposer] = None
    current_feature: Optional[dict] = None
    selected_skills: list[SkillMetadata] = []

    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                elif msg_type == "analyze":
                    # Start analysis - select skills for feature
                    feature_data = message.get("feature", {})

                    name = feature_data.get("name", "").strip()
                    category = feature_data.get("category", "").strip()
                    description = feature_data.get("description", "").strip()
                    steps = feature_data.get("steps", [])

                    if not name or not description:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Feature name and description are required"
                        })
                        continue

                    current_feature = {
                        "name": name,
                        "category": category or "uncategorized",
                        "description": description,
                        "steps": steps,
                    }

                    # Select skills
                    await websocket.send_json({
                        "type": "status",
                        "content": "Selecting relevant skills..."
                    })

                    selector = get_skills_selector()

                    # Use AI-assisted selection for complex features
                    use_ai = len(description) > 100 or len(steps) > 3

                    if use_ai:
                        async for chunk in selector.select_skills_with_ai(
                            name=name,
                            description=description,
                            category=category,
                            steps=steps,
                            project_dir=project_dir,
                        ):
                            await websocket.send_json(chunk)
                    else:
                        # Simple keyword-based selection
                        result = selector.select_skills_for_feature(
                            name=name,
                            description=description,
                            category=category,
                            steps=steps,
                        )
                        await websocket.send_json({
                            "type": "skills_suggested",
                            "selection": result.to_dict()
                        })

                elif msg_type == "select_skills":
                    # User confirmed skill selection
                    skill_ids = message.get("skill_ids", [])

                    if not skill_ids:
                        await websocket.send_json({
                            "type": "error",
                            "content": "No skills selected"
                        })
                        continue

                    # Get skill metadata
                    catalog = get_skills_catalog()
                    selected_skills = []
                    for skill_id in skill_ids:
                        skill = catalog.get_skill(skill_id)
                        if skill:
                            selected_skills.append(skill)

                    await websocket.send_json({
                        "type": "status",
                        "content": f"Selected {len(selected_skills)} skills"
                    })

                    await websocket.send_json({
                        "type": "skills_confirmed",
                        "skills": [s.name for s in selected_skills]
                    })

                elif msg_type == "decompose":
                    # Decompose feature with selected skills
                    if not current_feature:
                        await websocket.send_json({
                            "type": "error",
                            "content": "No feature to decompose. Send 'analyze' first."
                        })
                        continue

                    # Allow overriding skills in this message
                    skill_ids = message.get("selected_skills", [])
                    if skill_ids:
                        catalog = get_skills_catalog()
                        selected_skills = []
                        for skill_id in skill_ids:
                            skill = catalog.get_skill(skill_id)
                            if skill:
                                selected_skills.append(skill)

                    if not selected_skills:
                        await websocket.send_json({
                            "type": "error",
                            "content": "No skills selected. Send 'select_skills' first."
                        })
                        continue

                    # Create decomposer and stream results
                    decomposer = await create_decomposer(selected_skills)

                    async for chunk in decomposer.decompose_stream(
                        name=current_feature["name"],
                        category=current_feature["category"],
                        description=current_feature["description"],
                        steps=current_feature["steps"],
                        project_dir=project_dir,
                    ):
                        await websocket.send_json(chunk)

                elif msg_type == "update_task":
                    # Client is updating a task locally - just acknowledge
                    task_id = message.get("task_id")
                    updates = message.get("updates", {})

                    await websocket.send_json({
                        "type": "task_updated",
                        "task_id": task_id,
                        "updates": updates,
                    })

                elif msg_type == "confirm":
                    # Client confirmed final task selection
                    tasks = message.get("tasks", [])

                    await websocket.send_json({
                        "type": "tasks_confirmed",
                        "count": len(tasks),
                        "message": f"Confirmed {len(tasks)} tasks for creation"
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Unknown message type: {msg_type}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "content": "Invalid JSON"
                })

    except WebSocketDisconnect:
        logger.info(f"Skills analysis WebSocket disconnected for {project_name}")

    except Exception as e:
        logger.exception(f"Skills analysis WebSocket error for {project_name}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"Server error: {str(e)}"
            })
        except Exception:
            pass

    finally:
        # Clean up
        if decomposer:
            try:
                await decomposer.close()
            except Exception:
                pass
