"""
Redesign Router
===============

FastAPI router for redesign-related endpoints. Provides REST API
for managing frontend redesign sessions, reference uploads,
token extraction, and phase approvals.
"""

import base64
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from registry import get_project_path
from server.services.redesign_service import RedesignService

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_create_database = None
_RedesignSession = None


def _get_db_classes():
    """Lazy import of database classes."""
    global _create_database, _RedesignSession
    if _create_database is None:
        import sys
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from api.database import RedesignSession, create_database
        _create_database = create_database
        _RedesignSession = RedesignSession
    return _create_database, _RedesignSession


@contextmanager
def get_db_session(project_dir: Path):
    """
    Context manager for database sessions.
    Creates a project-specific session and ensures it is closed.
    """
    create_database, _ = _get_db_classes()
    _, SessionLocal = create_database(project_dir)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

router = APIRouter(prefix="/api/projects/{project_name}/redesign", tags=["redesign"])


# ============================================================================
# Pydantic Models
# ============================================================================


class StartRedesignRequest(BaseModel):
    """Request to start a new redesign session."""
    pass  # No additional fields needed, project_name comes from path


class AddReferenceRequest(BaseModel):
    """Request to add a reference to a session."""
    ref_type: str  # 'image', 'url', 'figma'
    data: str  # base64 for images, URL string for others
    metadata: Optional[dict] = None


class ApprovePhaseRequest(BaseModel):
    """Request to approve a redesign phase."""
    phase: str
    modifications: Optional[dict] = None
    comment: Optional[str] = None


class RedesignSessionResponse(BaseModel):
    """Response containing redesign session details."""
    id: int
    project_name: str
    status: str
    current_phase: Optional[str]
    references: Optional[list]
    extracted_tokens: Optional[dict]
    change_plan: Optional[dict]
    framework_detected: Optional[str]
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


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/start", response_model=RedesignSessionResponse)
async def start_redesign_session(
    project_name: str,
):
    """
    Start a new redesign session for a project.

    Creates a new session in 'collecting' status, ready to receive
    reference images, URLs, or Figma links.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        # Check for existing active session
        existing = await service.get_active_session(project_name)
        if existing:
            return existing.to_dict()

        session = await service.create_session(project_name)
        return session.to_dict()


@router.get("/status", response_model=RedesignSessionResponse)
async def get_redesign_status(
    project_name: str,
):
    """
    Get the status of the active redesign session.

    Returns the current session with its status, references,
    extracted tokens, and change plan.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        return session.to_dict()


@router.post("/upload-reference")
async def upload_reference(
    project_name: str,
    file: UploadFile = File(...),
):
    """
    Upload an image reference for the redesign.

    Accepts PNG, JPG, or WebP images. The image is stored as
    base64 in the session.
    """
    project_dir = get_project_dir(project_name)

    # Validate file type first (before opening db session)
    allowed_types = ["image/png", "image/jpeg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )

    # Read and encode file
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    image_base64 = base64.b64encode(content).decode("utf-8")

    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        # Add reference
        session = await service.add_reference(
            session.id,
            ref_type="image",
            data=image_base64,
            metadata={
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(content),
            }
        )

        return {"status": "ok", "references_count": len(session.references or [])}


@router.post("/add-url-reference")
async def add_url_reference(
    project_name: str,
    request: AddReferenceRequest,
):
    """
    Add a URL reference for the redesign.

    The system will capture a screenshot of the URL and store it
    for design token extraction.
    """
    if request.ref_type != "url":
        raise HTTPException(status_code=400, detail="Expected ref_type='url'")

    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        try:
            session = await service.add_reference(
                session.id,
                ref_type="url",
                data=request.data,
                metadata=request.metadata,
            )
            return {"status": "ok", "references_count": len(session.references or [])}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/extract-tokens")
async def extract_tokens(
    project_name: str,
):
    """
    Extract design tokens from all references.

    Uses Claude Vision API to analyze reference images and extract
    colors, typography, spacing, and other design tokens.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        if not session.references:
            raise HTTPException(status_code=400, detail="No references uploaded")

        try:
            session = await service.extract_tokens(session.id)
            return {
                "status": "ok",
                "tokens": session.extracted_tokens,
            }
        except Exception as e:
            logger.error(f"Token extraction failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/tokens")
async def get_tokens(
    project_name: str,
):
    """
    Get the extracted design tokens.

    Returns the tokens that were extracted from the references.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        if not session.extracted_tokens:
            raise HTTPException(status_code=400, detail="Tokens not yet extracted")

        return session.extracted_tokens


@router.post("/generate-plan")
async def generate_plan(
    project_name: str,
):
    """
    Generate an implementation plan.

    Detects the project framework and generates a plan for
    applying the design tokens to the codebase.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        if not session.extracted_tokens:
            raise HTTPException(status_code=400, detail="Tokens not yet extracted")

        try:
            session = await service.generate_plan(session.id)
            return {
                "status": "ok",
                "framework": session.framework_detected,
                "plan": session.change_plan,
            }
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan")
async def get_plan(
    project_name: str,
):
    """
    Get the generated change plan.

    Returns the plan showing which files will be modified
    and what changes will be made.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        if not session.change_plan:
            raise HTTPException(status_code=400, detail="Plan not yet generated")

        return {
            "framework": session.framework_detected,
            "plan": session.change_plan,
        }


@router.post("/approve-phase")
async def approve_phase(
    project_name: str,
    request: ApprovePhaseRequest,
):
    """
    Approve a phase of the redesign plan.

    User must approve each phase before the agent can proceed
    with implementation.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        session = await service.approve_phase(
            session.id,
            request.phase,
            request.modifications,
            request.comment,
        )

        return {
            "status": "ok",
            "phase": request.phase,
            "session_status": session.status,
        }


@router.get("/approval/{phase}")
async def check_approval(
    project_name: str,
    phase: str,
):
    """
    Check if a phase has been approved.

    Used by the agent to wait for user approval before
    proceeding with implementation.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        approval = await service.get_phase_approval(session.id, phase)

        return {
            "phase": phase,
            "approved": approval is not None,
            "modifications": approval.modifications if approval else None,
        }


@router.post("/complete")
async def complete_session(
    project_name: str,
):
    """
    Mark the redesign session as complete.

    Called after all phases have been implemented and verified.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        session = await service.complete_session(session.id)

        return {
            "status": "complete",
            "session_id": session.id,
        }


@router.delete("/cancel")
async def cancel_session(
    project_name: str,
):
    """
    Cancel and delete the active redesign session.

    Removes all data associated with the session.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = RedesignService(db, project_dir)

        session = await service.get_active_session(project_name)
        if not session:
            raise HTTPException(status_code=404, detail="No active redesign session")

        session_id = session.id
        db.delete(session)
        db.commit()

        logger.info(f"Cancelled redesign session {session_id}")

        return {
            "status": "cancelled",
            "session_id": session_id,
        }
