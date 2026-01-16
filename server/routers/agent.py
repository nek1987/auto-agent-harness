"""
Agent Router
============

API endpoints for agent control (start/stop/pause/resume).
Uses project registry for path lookups.
"""

import logging
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import AgentActionResponse, AgentStartRequest, AgentStatus
from ..services.process_manager import get_manager

# Lazy imports to avoid circular dependencies
_create_database = None
_RedesignSession = None

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
    Ensures session is always closed, even on exceptions.
    """
    create_database, _ = _get_db_classes()
    _, SessionLocal = create_database(project_dir)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


router = APIRouter(prefix="/api/projects/{project_name}/agent", tags=["agent"])

# Root directory for process manager
ROOT_DIR = Path(__file__).parent.parent.parent


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name"
        )
    return name


def get_project_manager(project_name: str):
    """Get the process manager for a project."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    return get_manager(project_name, project_dir, ROOT_DIR)


def _mark_redesign_session_extracting(project_name: str, project_dir: Path) -> None:
    """Mark active redesign session as extracting when planner starts."""
    try:
        with get_db_session(project_dir) as db:
            _, RedesignSession = _get_db_classes()
            session = (
                db.query(RedesignSession)
                .filter(
                    RedesignSession.project_name == project_name,
                    RedesignSession.status != "complete",
                    RedesignSession.status != "failed",
                )
                .order_by(RedesignSession.created_at.desc())
                .first()
            )
            if not session or session.status != "collecting":
                return

            session.status = "extracting"
            session.current_phase = "tokens"
            session.updated_at = datetime.utcnow()
            db.commit()
    except Exception as exc:
        logger.warning("Failed to update redesign session status: %s", exc)


@router.get("/status", response_model=AgentStatus)
async def get_agent_status(project_name: str):
    """Get the current status of the agent for a project."""
    manager = get_project_manager(project_name)

    # Run healthcheck to detect crashed processes
    await manager.healthcheck()

    return AgentStatus(
        status=manager.status,
        pid=manager.pid,
        started_at=manager.started_at,
        yolo_mode=manager.yolo_mode,
        mode=manager.mode,
    )


@router.post("/start", response_model=AgentActionResponse)
async def start_agent(
    project_name: str,
    request: AgentStartRequest = AgentStartRequest(),
):
    """Start the agent for a project."""
    manager = get_project_manager(project_name)

    success, message = await manager.start(yolo_mode=request.yolo_mode, mode=request.mode)

    if success and request.mode == "redesign":
        project_dir = _get_project_path(project_name)
        if project_dir:
            _mark_redesign_session_extracting(project_name, project_dir)

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/stop", response_model=AgentActionResponse)
async def stop_agent(project_name: str):
    """Stop the agent for a project."""
    manager = get_project_manager(project_name)

    success, message = await manager.stop()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/pause", response_model=AgentActionResponse)
async def pause_agent(project_name: str):
    """Pause the agent for a project."""
    manager = get_project_manager(project_name)

    success, message = await manager.pause()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/resume", response_model=AgentActionResponse)
async def resume_agent(project_name: str):
    """Resume a paused agent."""
    manager = get_project_manager(project_name)

    success, message = await manager.resume()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )
