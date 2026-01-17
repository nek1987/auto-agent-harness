"""
Component Reference Router
==========================

FastAPI router for component reference-related endpoints. Provides REST API
for managing component reference sessions, ZIP uploads, analysis triggers,
and feature linking.
"""

import asyncio
import base64
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from registry import get_project_path
from ..services.component_reference_service import ComponentReferenceService

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_create_database = None
_ComponentReferenceSession = None


def _get_db_classes():
    """Lazy import of database classes."""
    global _create_database, _ComponentReferenceSession
    if _create_database is None:
        import sys
        from pathlib import Path
        root = Path(__file__).parent.parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from api.database import ComponentReferenceSession, create_database
        _create_database = create_database
        _ComponentReferenceSession = ComponentReferenceSession
    return _create_database, _ComponentReferenceSession


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


class GenerateFeaturesRequest(BaseModel):
    """Request to generate features from component references."""
    force: bool = False


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




# ============================================================================
# Endpoints
# ============================================================================


@router.post("/start", response_model=ComponentReferenceSessionResponse)
async def start_session(
    project_name: str,
    request: StartSessionRequest,
):
    """
    Start a new component reference session for a project.

    Creates a new session in 'uploading' status, ready to receive
    component files from ZIP or direct upload.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Get the status of the active component reference session.

    Returns the current session with its status, components,
    analysis, and generation plan.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
    redesign_session_id: Optional[int] = Form(None),
    page_identifier: Optional[str] = Form(None),
    display_name: Optional[str] = Form(None),
    match_keywords: str = Form("[]"),
):
    """
    Upload a ZIP file with component code.

    Extracts React/Vue/Svelte components from the ZIP and stores
    them for analysis. Automatically detects framework and file types.

    If redesign_session_id is provided, links this component session
    to the redesign session for integrated token extraction.

    If page_identifier is provided (e.g., "/login", "/dashboard"), creates
    a PageReference linking these components to that specific page.
    This enables page-specific component matching during feature implementation.
    """
    import json as json_lib

    # Parse match_keywords
    try:
        keywords = json_lib.loads(match_keywords) if match_keywords else []
    except json_lib.JSONDecodeError:
        keywords = []
    # Validate file type first
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a ZIP archive")

    # Read file content
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        page_ref = None

        # If page_identifier is provided, create session with page reference
        if page_identifier:
            # Ensure page_identifier starts with /
            if not page_identifier.startswith("/"):
                page_identifier = "/" + page_identifier

            session, page_ref = await service.create_session_for_page(
                project_name=project_name,
                page_identifier=page_identifier,
                source_type=source_type,
                source_url=source_url,
                display_name=display_name,
                match_keywords=keywords if keywords else None,
            )
        else:
            # Standard flow: check or create session
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

        try:
            session = await service.parse_zip_file(
                session.id,
                content,
                filename=file.filename,
            )

            # Link to redesign session if provided
            linked_redesign_id = None
            if redesign_session_id:
                linked_redesign_id = await service.link_to_redesign_session(
                    session.id,
                    redesign_session_id,
                )

            response = {
                "status": "ok",
                "session_id": session.id,
                "components_count": len(session.components or []),
                "linked_redesign_session_id": linked_redesign_id,
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

            # Include page reference info if created
            if page_ref:
                response["page_reference_id"] = page_ref.id
                response["page_identifier"] = page_identifier
                response["filename"] = file.filename

            return response
        except Exception as e:
            logger.error(f"ZIP parsing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-components")
async def add_components(
    project_name: str,
    request: AddComponentsRequest,
):
    """
    Add components directly (not from ZIP).

    Use this to add component code from clipboard or other sources.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Get the uploaded components.

    Returns list of components with their metadata (without full content).
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Get the full content of a specific component.

    Returns the component code for review.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Start analysis of uploaded components.

    Updates session status to 'analyzing'. The actual analysis
    is performed by the MCP server via Claude.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Get the analysis results.

    Returns the extracted patterns, styling approach, and dependencies.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Save analysis results (called by MCP server after Claude analysis).

    Moves session to 'planning' status.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Generate a component creation plan.

    Creates a plan for generating new components based on the analysis.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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


@router.post("/generate-features")
async def generate_features(
    project_name: str,
    request: GenerateFeaturesRequest = GenerateFeaturesRequest(),
):
    """
    Generate feature tasks from the active component reference session.

    Uses AI analysis to suggest features and creates them in the database.
    """
    from prompts import extract_spec_metadata, get_app_spec

    project_dir = get_project_dir(project_name)

    # Lazy import to avoid circular dependencies
    import sys
    root = Path(__file__).parent.parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from api.database import Feature, PageReference

    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)
        session = await service.get_active_session(project_name)

        if not session:
            raise HTTPException(status_code=404, detail="No active component reference session")

        if not session.components:
            raise HTTPException(status_code=400, detail="No components uploaded to analyze")

        existing = db.query(Feature).filter(
            Feature.reference_session_id == session.id
        ).count()
        if existing and not request.force:
            return {
                "generated": 0,
                "existing": existing,
                "message": "Features already generated for this session",
            }

        feature_count = None
        try:
            spec_content = get_app_spec(project_dir)
            _, feature_count, _ = extract_spec_metadata(spec_content)
        except Exception as exc:
            logger.info(f"Unable to read feature_count from app_spec: {exc}")

        analysis = await service.ai_analyze_components_for_features(
            session,
            feature_count=feature_count,
        )

        suggested_features = analysis.get("suggested_features", [])
        if not suggested_features:
            return {
                "generated": 0,
                "existing": existing,
                "message": "No features suggested from component analysis",
                "analysis_summary": analysis.get("analysis_summary", ""),
            }

        page_ref = db.query(PageReference).filter(
            PageReference.reference_session_id == session.id
        ).first()

        max_priority_result = db.query(Feature.priority).order_by(
            Feature.priority.desc()
        ).first()
        start_priority = (max_priority_result[0] + 1) if max_priority_result else 1

        created = 0
        for i, feat_data in enumerate(suggested_features):
            feature = Feature(
                priority=start_priority + i,
                category=feat_data.get("category", "components"),
                name=feat_data.get("name", f"Feature {i + 1}"),
                description=feat_data.get("description", ""),
                steps=feat_data.get("steps", []),
                dependencies=feat_data.get("dependencies", []),
                arch_layer=feat_data.get("arch_layer", 6),
                reference_session_id=session.id,
                page_reference_id=page_ref.id if page_ref else None,
                item_type="feature",
                passes=False,
                in_progress=False,
            )
            db.add(feature)
            created += 1

        db.commit()

        return {
            "generated": created,
            "existing": existing,
            "feature_count": feature_count,
            "target_range": analysis.get("target_range"),
            "analysis_summary": analysis.get("analysis_summary", ""),
        }


@router.get("/plan")
async def get_plan(
    project_name: str,
):
    """
    Get the generation plan.

    Returns the plan for creating new components.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Link the component reference session to a feature.

    When a feature has a reference linked, the coding agent
    will use the analysis as context during implementation.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Get the reference context for a feature.

    Returns the analysis and plan from the linked session.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Mark the component reference session as complete.

    Called after components have been created based on the reference.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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
):
    """
    Cancel and delete the active component reference session.

    Removes all data associated with the session.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

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


# ============================================================================
# Multi-Page Reference Endpoints
# ============================================================================


class PageReferenceRequest(BaseModel):
    """Request to create or update a page reference."""
    display_name: Optional[str] = None
    match_keywords: Optional[List[str]] = None


class LinkFeatureToPageRequest(BaseModel):
    """Request to link a feature to a page reference."""
    page_reference_id: int


@router.get("/pages")
async def scan_project_pages(
    project_name: str,
):
    """
    Scan the project and detect all pages/routes.

    Analyzes the project structure to identify:
    - Framework routing type (Next.js, React Router, etc.)
    - All pages with their routes
    - Layout components

    Includes a 10-second timeout to prevent infinite scanning.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        try:
            # Run scan with 10 second timeout to prevent infinite loops
            result = await asyncio.wait_for(
                service.scan_project_pages(),
                timeout=10.0
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Page scan timed out for {project_name}")
            return {
                "pages": [],
                "layouts": [],
                "framework_type": "unknown",
                "error": "Scan timed out - project may be too large or contain circular symlinks"
            }
        except Exception as e:
            logger.error(f"Project scan failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/references")
async def list_page_references(
    project_name: str,
):
    """
    List all page references for the project.

    Returns all pages that have component reference sessions linked.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)
        _, ComponentReferenceSession = _get_db_classes()

        refs = await service.list_page_references(project_name)

        return {
            "total": len(refs),
            "references": [
                {
                    **ref.to_dict(),
                    "session_status": (
                        db.query(ComponentReferenceSession)
                        .filter(ComponentReferenceSession.id == ref.reference_session_id)
                        .first()
                    ).status if ref.reference_session_id else None,
                }
                for ref in refs
            ],
        }


@router.post("/pages/{page_identifier:path}/upload-zip")
async def upload_zip_for_page(
    project_name: str,
    page_identifier: str,
    file: UploadFile = File(...),
    source_type: str = Form("custom"),
    source_url: str = Form(None),
    display_name: str = Form(None),
    match_keywords: str = Form("[]"),
):
    """
    Upload a ZIP file with component code for a specific page.

    Creates a new session and page reference, then extracts components
    from the ZIP file.
    """
    import json

    # Ensure page_identifier starts with /
    if not page_identifier.startswith("/"):
        page_identifier = "/" + page_identifier

    # Parse keywords
    try:
        keywords = json.loads(match_keywords) if match_keywords else []
    except json.JSONDecodeError:
        keywords = []

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a ZIP archive")

    # Read file content
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        try:
            # Create session and page reference
            session, page_ref = await service.create_session_for_page(
                project_name=project_name,
                page_identifier=page_identifier,
                source_type=source_type,
                source_url=source_url,
                display_name=display_name,
                match_keywords=keywords if keywords else None,
            )

            # Parse ZIP file
            session = await service.parse_zip_file(
                session.id,
                content,
                filename=file.filename,
            )

            return {
                "status": "ok",
                "session_id": session.id,
                "page_reference": page_ref.to_dict(),
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
            logger.error(f"ZIP upload for page failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/references/{page_identifier:path}/bind")
async def bind_reference_to_page(
    project_name: str,
    page_identifier: str,
    session_id: int,
    request: PageReferenceRequest = None,
):
    """
    Bind an existing session to a page.

    Creates or updates a PageReference linking the page to the session.
    """
    # Ensure page_identifier starts with /
    if not page_identifier.startswith("/"):
        page_identifier = "/" + page_identifier

    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        # Verify session exists
        session = await service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        try:
            ref = await service.create_page_reference(
                project_name=project_name,
                page_identifier=page_identifier,
                session_id=session_id,
                display_name=request.display_name if request else None,
                match_keywords=request.match_keywords if request else None,
            )

            return {
                "status": "ok",
                "page_reference": ref.to_dict(),
            }
        except Exception as e:
            logger.error(f"Bind reference failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/references/{page_identifier:path}")
async def get_page_reference(
    project_name: str,
    page_identifier: str,
):
    """
    Get details for a specific page reference.
    """
    # Ensure page_identifier starts with /
    if not page_identifier.startswith("/"):
        page_identifier = "/" + page_identifier

    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        ref = await service.get_page_reference(project_name, page_identifier)
        if not ref:
            raise HTTPException(
                status_code=404,
                detail=f"Page reference for '{page_identifier}' not found"
            )

        result = ref.to_dict()

        # Add session info
        if ref.reference_session_id:
            session = await service.get_session(ref.reference_session_id)
            if session:
                result["session_status"] = session.status
                result["components_count"] = len(session.components or [])
                result["has_analysis"] = session.extracted_analysis is not None

        return result


@router.delete("/references/{page_identifier:path}")
async def delete_page_reference(
    project_name: str,
    page_identifier: str,
):
    """
    Delete a page reference.

    Does not delete the associated session, just the page binding.
    """
    # Ensure page_identifier starts with /
    if not page_identifier.startswith("/"):
        page_identifier = "/" + page_identifier

    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        deleted = await service.delete_page_reference(project_name, page_identifier)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Page reference for '{page_identifier}' not found"
            )

        return {"status": "deleted", "page_identifier": page_identifier}


@router.get("/features/{feature_id}/auto-reference")
async def get_auto_reference_for_feature(
    project_name: str,
    feature_id: int,
):
    """
    Get the auto-matched page reference for a feature.

    Uses keyword matching to find the best page reference based on
    the feature's category, name, and description.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        result = await service.get_auto_reference_for_feature(project_name, feature_id)
        if not result:
            return {
                "matched": False,
                "feature_id": feature_id,
                "message": "No matching page reference found"
            }

        return {
            "matched": True,
            "feature_id": feature_id,
            **result,
        }


@router.post("/features/{feature_id}/link-to-page")
async def link_feature_to_page_reference(
    project_name: str,
    feature_id: int,
    request: LinkFeatureToPageRequest,
):
    """
    Link a feature directly to a page reference.

    Sets the feature's page_reference_id, which takes priority
    over auto-matching.
    """
    project_dir = get_project_dir(project_name)
    with get_db_session(project_dir) as db:
        service = ComponentReferenceService(db, project_dir)

        try:
            feature = await service.link_feature_to_page_reference(
                feature_id,
                request.page_reference_id,
            )
            return {
                "status": "ok",
                "feature_id": feature.id,
                "feature_name": feature.name,
                "page_reference_id": request.page_reference_id,
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
