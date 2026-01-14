"""
Component Reference Router
==========================

FastAPI router for component reference-related endpoints. Provides REST API
for managing component reference sessions, ZIP uploads, analysis triggers,
and feature linking.
"""

import base64
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db, ComponentReferenceSession
from registry import get_project_path
from server.services.component_reference_service import ComponentReferenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_name}/component-reference", tags=["component-reference"])


# ============================================================================
# Pydantic Models
# ============================================================================


class StartSessionRequest(BaseModel):
    """Request to start a new component reference session."""
    source_type: str = "custom"  # 'v0', 'shadcn', 'custom'
    source_url: Optional[str] = None


class AddComponentsRequest(BaseModel):
    """Request to add components directly (not from ZIP)."""
    components: List[dict]  # [{filename, content, framework?}]


class GeneratePlanRequest(BaseModel):
    """Request to generate a component creation plan."""
    target_components: List[str]  # Component names to create
    adaptation_notes: Optional[str] = None


class LinkFeatureRequest(BaseModel):
    """Request to link session to a feature."""
    feature_id: int


class ComponentReferenceSessionResponse(BaseModel):
    """Response containing component reference session details."""
    id: int
    project_name: str
    status: str
    source_type: str
    source_url: Optional[str]
    components: Optional[list]
    extracted_analysis: Optional[dict]
    generation_plan: Optional[dict]
    generated_components: Optional[dict]
    target_framework: Optional[str]
    error_message: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


# ============================================================================
# Helper Functions
# ============================================================================


def get_project_dir(project_name: str) -> Path:
    """Get the project directory from registry."""
    project_path = get_project_path(project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
    return Path(project_path)


def get_component_reference_service(project_name: str, db: Session) -> ComponentReferenceService:
    """Create a ComponentReferenceService instance for the project."""
    project_dir = get_project_dir(project_name)
    return ComponentReferenceService(db, project_dir)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/start", response_model=ComponentReferenceSessionResponse)
async def start_session(
    project_name: str,
    request: StartSessionRequest,
    db: Session = Depends(get_db),
):
    """
    Start a new component reference session for a project.

    Creates a new session in 'uploading' status, ready to receive
    component files from ZIP or direct upload.
    """
    service = get_component_reference_service(project_name, db)

    # Check for existing active session
    existing = await service.get_active_session(project_name)
    if existing:
        return existing.to_dict()

    session = await service.create_session(
        project_name,
        source_type=request.source_type,
        source_url=request.source_url,
    )
    return session.to_dict()


@router.get("/status", response_model=ComponentReferenceSessionResponse)
async def get_session_status(
    project_name: str,
    db: Session = Depends(get_db),
):
    """
    Get the status of the active component reference session.

    Returns the current session with its status, components,
    analysis, and generation plan.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    return session.to_dict()


@router.post("/upload-zip")
async def upload_zip(
    project_name: str,
    file: UploadFile = File(...),
    source_type: str = Form("custom"),
    source_url: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a ZIP file with component code.

    Extracts React/Vue/Svelte components from the ZIP and stores
    them for analysis. Automatically detects framework and file types.
    """
    service = get_component_reference_service(project_name, db)

    # Check or create session
    session = await service.get_active_session(project_name)
    if not session:
        session = await service.create_session(
            project_name,
            source_type=source_type,
            source_url=source_url,
        )

    if session.status != "uploading":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upload to session in status: {session.status}"
        )

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a ZIP archive")

    # Read file content
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    try:
        session = await service.parse_zip_file(
            session.id,
            content,
            filename=file.filename,
        )
        return {
            "status": "ok",
            "session_id": session.id,
            "components_count": len(session.components or []),
            "components": [
                {
                    "filename": c["filename"],
                    "framework": c["framework"],
                    "file_type": c["file_type"],
                    "size": c["size"],
                }
                for c in (session.components or [])
            ],
        }
    except Exception as e:
        logger.error(f"ZIP parsing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-components")
async def add_components(
    project_name: str,
    request: AddComponentsRequest,
    db: Session = Depends(get_db),
):
    """
    Add components directly (not from ZIP).

    Use this to add component code from clipboard or other sources.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    if session.status != "uploading":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add components in status: {session.status}"
        )

    try:
        session = await service.add_components(session.id, request.components)
        return {
            "status": "ok",
            "components_count": len(session.components or []),
        }
    except Exception as e:
        logger.error(f"Add components failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/components")
async def get_components(
    project_name: str,
    db: Session = Depends(get_db),
):
    """
    Get the uploaded components.

    Returns list of components with their metadata (without full content).
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    if not session.components:
        return {"components": []}

    return {
        "components": [
            {
                "filename": c["filename"],
                "filepath": c.get("filepath"),
                "framework": c["framework"],
                "file_type": c["file_type"],
                "size": c["size"],
                "added_at": c.get("added_at"),
            }
            for c in session.components
        ]
    }


@router.get("/component/{filename}")
async def get_component_content(
    project_name: str,
    filename: str,
    db: Session = Depends(get_db),
):
    """
    Get the full content of a specific component.

    Returns the component code for review.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    if not session.components:
        raise HTTPException(status_code=404, detail="No components uploaded")

    for comp in session.components:
        if comp["filename"] == filename:
            return {
                "filename": comp["filename"],
                "content": comp["content"],
                "framework": comp["framework"],
                "file_type": comp["file_type"],
            }

    raise HTTPException(status_code=404, detail=f"Component '{filename}' not found")


@router.post("/analyze")
async def start_analysis(
    project_name: str,
    db: Session = Depends(get_db),
):
    """
    Start analysis of uploaded components.

    Updates session status to 'analyzing'. The actual analysis
    is performed by the MCP server via Claude.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    if not session.components:
        raise HTTPException(status_code=400, detail="No components uploaded")

    try:
        session = await service.start_analysis(session.id)
        return {
            "status": "ok",
            "session_status": session.status,
            "message": "Analysis started. Use MCP tools to perform actual analysis.",
        }
    except Exception as e:
        logger.error(f"Analysis start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis")
async def get_analysis(
    project_name: str,
    db: Session = Depends(get_db),
):
    """
    Get the analysis results.

    Returns the extracted patterns, styling approach, and dependencies.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    if not session.extracted_analysis:
        raise HTTPException(status_code=400, detail="Analysis not yet completed")

    return {
        "analysis": session.extracted_analysis,
        "target_framework": session.target_framework,
    }


@router.post("/save-analysis")
async def save_analysis(
    project_name: str,
    analysis: dict,
    db: Session = Depends(get_db),
):
    """
    Save analysis results (called by MCP server after Claude analysis).

    Moves session to 'planning' status.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    try:
        session = await service.save_analysis(session.id, analysis)
        return {
            "status": "ok",
            "session_status": session.status,
        }
    except Exception as e:
        logger.error(f"Save analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-plan")
async def generate_plan(
    project_name: str,
    request: GeneratePlanRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a component creation plan.

    Creates a plan for generating new components based on the analysis.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    if not session.extracted_analysis:
        raise HTTPException(status_code=400, detail="Analysis not yet completed")

    # Build plan based on analysis and target components
    plan = {
        "target_framework": session.target_framework,
        "components_to_create": [
            {
                "name": name,
                "based_on": None,  # Will be matched by MCP
                "patterns_to_apply": session.extracted_analysis.get("common_patterns", []),
                "styling_approach": session.extracted_analysis.get("styling_approach"),
                "adaptations": request.adaptation_notes,
            }
            for name in request.target_components
        ],
        "dependencies_needed": session.extracted_analysis.get("dependencies", []),
    }

    try:
        session = await service.save_plan(session.id, plan)
        return {
            "status": "ok",
            "plan": plan,
        }
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan")
async def get_plan(
    project_name: str,
    db: Session = Depends(get_db),
):
    """
    Get the generation plan.

    Returns the plan for creating new components.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    if not session.generation_plan:
        raise HTTPException(status_code=400, detail="Plan not yet generated")

    return {
        "plan": session.generation_plan,
        "target_framework": session.target_framework,
    }


@router.post("/apply-to-feature/{feature_id}")
async def apply_to_feature(
    project_name: str,
    feature_id: int,
    db: Session = Depends(get_db),
):
    """
    Link the component reference session to a feature.

    When a feature has a reference linked, the coding agent
    will use the analysis as context during implementation.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    try:
        feature = await service.link_to_feature(session.id, feature_id)
        return {
            "status": "ok",
            "feature_id": feature.id,
            "feature_name": feature.name,
            "session_id": session.id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/feature/{feature_id}/reference-context")
async def get_feature_reference_context(
    project_name: str,
    feature_id: int,
    db: Session = Depends(get_db),
):
    """
    Get the reference context for a feature.

    Returns the analysis and plan from the linked session.
    """
    service = get_component_reference_service(project_name, db)

    context = await service.get_reference_context(feature_id)
    if not context:
        raise HTTPException(
            status_code=404,
            detail=f"Feature {feature_id} has no linked component reference"
        )

    return context


@router.post("/complete")
async def complete_session(
    project_name: str,
    db: Session = Depends(get_db),
):
    """
    Mark the component reference session as complete.

    Called after components have been created based on the reference.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    session = await service.complete_session(session.id)

    return {
        "status": "complete",
        "session_id": session.id,
    }


@router.delete("/cancel")
async def cancel_session(
    project_name: str,
    db: Session = Depends(get_db),
):
    """
    Cancel and delete the active component reference session.

    Removes all data associated with the session.
    """
    service = get_component_reference_service(project_name, db)

    session = await service.get_active_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active component reference session")

    session_id = session.id
    await service.cancel_session(session_id)

    logger.info(f"Cancelled component reference session {session_id}")

    return {
        "status": "cancelled",
        "session_id": session_id,
    }
