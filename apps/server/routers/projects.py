"""
Projects Router
===============

API endpoints for project management.
Uses project registry for path lookups instead of fixed generations/ directory.
"""

import logging
import os
import re
import shutil
import stat
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..services.process_manager import check_agent_lock
from ..schemas import (
    ImportFeaturesRequest,
    ImportFeaturesResponse,
    ProjectCreate,
    ProjectDetail,
    ProjectPrompts,
    ProjectPromptsUpdate,
    ProjectStats,
    ProjectSummary,
)

# Lazy imports to avoid circular dependencies
_imports_initialized = False
_check_spec_exists = None
_scaffold_project_prompts = None
_get_project_prompts_dir = None
_count_passing_tests = None


def _init_imports():
    """Lazy import of project-level modules."""
    global _imports_initialized, _check_spec_exists
    global _scaffold_project_prompts, _get_project_prompts_dir
    global _count_passing_tests

    if _imports_initialized:
        return

    import sys
    root = Path(__file__).parent.parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from progress import count_passing_tests
    from prompts import get_project_prompts_dir, scaffold_project_prompts
    from start import check_spec_exists

    _check_spec_exists = check_spec_exists
    _scaffold_project_prompts = scaffold_project_prompts
    _get_project_prompts_dir = get_project_prompts_dir
    _count_passing_tests = count_passing_tests
    _imports_initialized = True


def _get_registry_functions():
    """Get registry functions with lazy import."""
    import sys
    root = Path(__file__).parent.parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import (
        get_project_path,
        list_registered_projects,
        register_project,
        unregister_project,
        validate_project_path,
    )
    return register_project, unregister_project, get_project_path, list_registered_projects, validate_project_path


router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name. Use only letters, numbers, hyphens, and underscores (1-50 chars)."
        )
    return name


def get_project_stats(project_dir: Path) -> ProjectStats:
    """Get statistics for a project."""
    _init_imports()
    passing, in_progress, total = _count_passing_tests(project_dir)
    percentage = (passing / total * 100) if total > 0 else 0.0
    return ProjectStats(
        passing=passing,
        in_progress=in_progress,
        total=total,
        percentage=round(percentage, 1)
    )


@router.get("", response_model=list[ProjectSummary])
async def list_projects():
    """List all registered projects."""
    _init_imports()
    _, _, _, list_registered_projects, validate_project_path = _get_registry_functions()

    projects = list_registered_projects()
    result = []

    for name, info in projects.items():
        project_dir = Path(info["path"])

        # Skip if path no longer exists
        is_valid, _ = validate_project_path(project_dir)
        if not is_valid:
            continue

        has_spec = _check_spec_exists(project_dir)
        stats = get_project_stats(project_dir)

        result.append(ProjectSummary(
            name=name,
            path=info["path"],
            has_spec=has_spec,
            stats=stats,
        ))

    return result


@router.post("", response_model=ProjectSummary)
async def create_project(project: ProjectCreate):
    """Create a new project at the specified path."""
    _init_imports()
    register_project, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(project.name)
    project_path = Path(project.path).resolve()

    # Check if project name already registered
    existing = get_project_path(name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Project '{name}' already exists at {existing}"
        )

    # Security: Check if path is in a blocked location
    from .filesystem import is_path_blocked
    if is_path_blocked(project_path):
        raise HTTPException(
            status_code=403,
            detail="Cannot create project in system or sensitive directory"
        )

    # Validate the path is usable
    if project_path.exists():
        if not project_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail="Path exists but is not a directory"
            )
    else:
        # Create the directory
        try:
            project_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create directory: {e}"
            )

    # Scaffold prompts
    _scaffold_project_prompts(project_path)

    # Register in registry
    try:
        register_project(name, project_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register project: {e}"
        )

    return ProjectSummary(
        name=name,
        path=project_path.as_posix(),
        has_spec=False,  # Just created, no spec yet
        stats=ProjectStats(passing=0, total=0, percentage=0.0),
    )


@router.get("/{name}", response_model=ProjectDetail)
async def get_project(name: str):
    """Get detailed information about a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory no longer exists: {project_dir}")

    has_spec = _check_spec_exists(project_dir)
    stats = get_project_stats(project_dir)
    prompts_dir = _get_project_prompts_dir(project_dir)

    return ProjectDetail(
        name=name,
        path=project_dir.as_posix(),
        has_spec=has_spec,
        stats=stats,
        prompts_dir=str(prompts_dir),
    )


@router.delete("/{name}")
async def delete_project(name: str, delete_files: bool = False):
    """
    Delete a project from the registry.

    Args:
        name: Project name to delete
        delete_files: If True, also delete the project directory and files
    """
    _init_imports()
    _, unregister_project, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    # Check if agent is running
    is_running, lock_cleared = check_agent_lock(project_dir)
    if is_running:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete project while agent is running. Stop the agent first."
        )
    if lock_cleared:
        logger.info("Cleared stale agent lock for project %s", name)

    # Optionally delete files
    if delete_files and project_dir.exists():
        try:
            errors: list[str] = []

            def _on_remove_error(func, path, exc_info):
                err = exc_info[1]
                if isinstance(err, FileNotFoundError):
                    return
                if isinstance(err, PermissionError):
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                        return
                    except Exception as inner:
                        errors.append(f"{path}: {inner}")
                        return
                errors.append(f"{path}: {err}")

            shutil.rmtree(project_dir, onerror=_on_remove_error)

            if errors:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to delete some project files: " + "; ".join(errors[:5]),
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete project files: {e}")

    # Unregister from registry
    unregister_project(name)

    return {
        "success": True,
        "message": f"Project '{name}' deleted" + (" (files removed)" if delete_files else " (files preserved)")
    }


@router.get("/{name}/prompts", response_model=ProjectPrompts)
async def get_project_prompts(name: str):
    """Get the content of project prompt files."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    prompts_dir = _get_project_prompts_dir(project_dir)

    def read_file(filename: str) -> str:
        filepath = prompts_dir / filename
        if filepath.exists():
            try:
                return filepath.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""

    return ProjectPrompts(
        app_spec=read_file("app_spec.txt"),
        initializer_prompt=read_file("initializer_prompt.md"),
        coding_prompt=read_file("coding_prompt.md"),
    )


@router.put("/{name}/prompts")
async def update_project_prompts(name: str, prompts: ProjectPromptsUpdate):
    """Update project prompt files."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    prompts_dir = _get_project_prompts_dir(project_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    def write_file(filename: str, content: str | None):
        if content is not None:
            filepath = prompts_dir / filename
            filepath.write_text(content, encoding="utf-8")

    write_file("app_spec.txt", prompts.app_spec)
    write_file("initializer_prompt.md", prompts.initializer_prompt)
    write_file("coding_prompt.md", prompts.coding_prompt)

    return {"success": True, "message": "Prompts updated"}


@router.get("/{name}/stats", response_model=ProjectStats)
async def get_project_stats_endpoint(name: str):
    """Get current progress statistics for a project."""
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    return get_project_stats(project_dir)


@router.post("/{name}/import", response_model=ImportFeaturesResponse)
async def import_project_features(name: str, import_data: ImportFeaturesRequest):
    """
    Import features for an existing project with pre-set statuses.

    This endpoint allows importing features from an existing project,
    marking them as passing (implemented) or pending (needs work).

    Args:
        name: Project name
        import_data: Features to import with their statuses
    """
    _init_imports()
    _, _, get_project_path, _, _ = _get_registry_functions()

    name = validate_project_name(name)
    project_dir = get_project_path(name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    # Check if agent is running
    is_running, lock_cleared = check_agent_lock(project_dir)
    if is_running:
        raise HTTPException(
            status_code=409,
            detail="Cannot import features while agent is running. Stop the agent first."
        )
    if lock_cleared:
        logger.info("Cleared stale agent lock for project %s", name)

    # Import features using the database module
    try:
        import sys
        root = Path(__file__).parent.parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from api.database import Feature, get_db_session

        db_path = project_dir / "features.db"
        session = get_db_session(db_path)

        try:
            # Optionally clear existing features
            if import_data.clear_existing:
                session.query(Feature).delete()
                session.commit()

            # Get next priority
            max_priority = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
            next_priority = (max_priority[0] + 1) if max_priority else 1

            # Import features
            passing_count = 0
            pending_count = 0

            for feature_data in import_data.features:
                db_feature = Feature(
                    priority=next_priority,
                    category=feature_data.category,
                    name=feature_data.name,
                    description=feature_data.description,
                    steps=feature_data.steps,
                    passes=feature_data.passes,
                    in_progress=False,
                    source_spec=feature_data.source_spec,
                    dependencies=feature_data.dependencies,
                )
                session.add(db_feature)
                next_priority += 1

                if feature_data.passes:
                    passing_count += 1
                else:
                    pending_count += 1

            session.commit()

            return ImportFeaturesResponse(
                success=True,
                imported=len(import_data.features),
                passing=passing_count,
                pending=pending_count,
                message=f"Successfully imported {len(import_data.features)} features "
                        f"({passing_count} passing, {pending_count} pending)"
            )

        finally:
            session.close()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import features: {e}"
        )
