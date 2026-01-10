"""
Spec Import Router
==================

API endpoints for importing and analyzing app_spec.txt files.

Features:
- Validate spec structure locally
- Analyze spec with Claude for quality assessment
- Import spec from file upload or content
- Approve spec and trigger feature creation
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

# Lazy imports to avoid circular dependencies
_imports_initialized = False
_validate_spec_structure = None
_import_spec_content = None
_get_project_prompts_dir = None
_SpecValidationResult = None

logger = logging.getLogger(__name__)


def _init_imports():
    """Lazy import of project-level modules."""
    global _imports_initialized, _validate_spec_structure
    global _import_spec_content, _get_project_prompts_dir
    global _SpecValidationResult

    if _imports_initialized:
        return

    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from prompts import (
        SpecValidationResult,
        get_project_prompts_dir,
        import_spec_content,
        validate_spec_structure,
    )

    _validate_spec_structure = validate_spec_structure
    _import_spec_content = import_spec_content
    _get_project_prompts_dir = get_project_prompts_dir
    _SpecValidationResult = SpecValidationResult
    _imports_initialized = True


def _get_registry_functions():
    """Get registry functions with lazy import."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path


def _get_analyzer():
    """Get SpecAnalyzer with lazy import."""
    from ..services.spec_analyzer import SpecAnalyzer
    return SpecAnalyzer()


router = APIRouter(prefix="/api/spec", tags=["spec-import"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ValidateSpecRequest(BaseModel):
    """Request to validate spec content."""
    spec_content: str = Field(..., description="The spec content to validate")


class ValidateSpecResponse(BaseModel):
    """Response from spec validation."""
    is_valid: bool
    score: int
    has_project_name: bool
    has_overview: bool
    has_tech_stack: bool
    has_feature_count: bool
    has_core_features: bool
    has_database_schema: bool
    has_api_endpoints: bool
    has_implementation_steps: bool
    has_success_criteria: bool
    project_name: Optional[str] = None
    feature_count: Optional[int] = None
    tech_stack: Optional[dict] = None
    missing_sections: list[str]
    warnings: list[str]
    errors: list[str]


class AnalyzeSpecRequest(BaseModel):
    """Request to analyze spec content with Claude."""
    spec_content: str = Field(..., description="The spec content to analyze")


class AnalyzeSpecResponse(BaseModel):
    """Response from spec analysis."""
    validation: ValidateSpecResponse
    strengths: list[str]
    improvements: list[str]
    critical_issues: list[str]
    suggested_changes: Optional[dict] = None
    analysis_model: str
    analysis_timestamp: str


class ImportSpecRequest(BaseModel):
    """Request to import spec content."""
    spec_content: str = Field(..., description="The spec content to import")
    spec_name: str = Field(default="main", description="Name for this spec")
    validate: bool = Field(default=True, description="Whether to validate before import")


class ImportSpecResponse(BaseModel):
    """Response from spec import."""
    success: bool
    path: str
    validation: Optional[ValidateSpecResponse] = None
    message: str


class ApproveSpecRequest(BaseModel):
    """Request to approve a spec and start processing."""
    apply_refinements: bool = Field(
        default=False,
        description="Whether to apply suggested refinements"
    )
    refinements: Optional[dict] = Field(
        default=None,
        description="Specific refinements to apply"
    )


class RefineSpecRequest(BaseModel):
    """Request to refine spec based on feedback."""
    spec_content: str = Field(..., description="Current spec content")
    feedback: str = Field(..., description="User feedback for refinement")


class RefineSpecResponse(BaseModel):
    """Response with refined spec."""
    success: bool
    refined_spec: str
    message: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/validate", response_model=ValidateSpecResponse)
async def validate_spec(request: ValidateSpecRequest):
    """
    Validate spec structure without Claude analysis.

    This performs fast local validation of the XML structure
    and required sections.
    """
    _init_imports()

    result = _validate_spec_structure(request.spec_content)

    return ValidateSpecResponse(
        is_valid=result.is_valid,
        score=result.score,
        has_project_name=result.has_project_name,
        has_overview=result.has_overview,
        has_tech_stack=result.has_tech_stack,
        has_feature_count=result.has_feature_count,
        has_core_features=result.has_core_features,
        has_database_schema=result.has_database_schema,
        has_api_endpoints=result.has_api_endpoints,
        has_implementation_steps=result.has_implementation_steps,
        has_success_criteria=result.has_success_criteria,
        project_name=result.project_name,
        feature_count=result.feature_count,
        tech_stack=result.tech_stack,
        missing_sections=result.missing_sections,
        warnings=result.warnings,
        errors=result.errors,
    )


@router.post("/analyze", response_model=AnalyzeSpecResponse)
async def analyze_spec(request: AnalyzeSpecRequest):
    """
    Analyze spec with Claude for deep quality assessment.

    This performs:
    1. Local validation
    2. Claude analysis for quality and completeness
    3. Suggestions for improvements
    """
    _init_imports()

    # Get analyzer
    analyzer = _get_analyzer()

    try:
        result = await analyzer.analyze(request.spec_content)

        return AnalyzeSpecResponse(
            validation=ValidateSpecResponse(
                is_valid=result.validation.is_valid,
                score=result.validation.score,
                has_project_name=result.validation.has_project_name,
                has_overview=result.validation.has_overview,
                has_tech_stack=result.validation.has_tech_stack,
                has_feature_count=result.validation.has_feature_count,
                has_core_features=result.validation.has_core_features,
                has_database_schema=result.validation.has_database_schema,
                has_api_endpoints=result.validation.has_api_endpoints,
                has_implementation_steps=result.validation.has_implementation_steps,
                has_success_criteria=result.validation.has_success_criteria,
                project_name=result.validation.project_name,
                feature_count=result.validation.feature_count,
                tech_stack=result.validation.tech_stack,
                missing_sections=result.validation.missing_sections,
                warnings=result.validation.warnings,
                errors=result.validation.errors,
            ),
            strengths=result.strengths,
            improvements=result.improvements,
            critical_issues=result.critical_issues,
            suggested_changes=result.suggested_changes,
            analysis_model=result.analysis_model,
            analysis_timestamp=result.analysis_timestamp,
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/import/{project_name}", response_model=ImportSpecResponse)
async def import_spec_to_project(
    project_name: str,
    request: ImportSpecRequest,
):
    """
    Import spec content into a project.

    The spec will be saved to the project's prompts directory
    and registered in the spec manifest.
    """
    _init_imports()
    get_project_path = _get_registry_functions()

    # Validate project name
    project_dir = get_project_path(project_name)
    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory no longer exists: {project_dir}"
        )

    # Check if agent is running
    lock_file = project_dir / ".agent.lock"
    if lock_file.exists():
        raise HTTPException(
            status_code=409,
            detail="Cannot import spec while agent is running. Stop the agent first."
        )

    try:
        dest_path, validation_result = _import_spec_content(
            project_dir=project_dir,
            content=request.spec_content,
            validate=request.validate,
            spec_name=request.spec_name,
        )

        validation_response = None
        if validation_result:
            validation_response = ValidateSpecResponse(
                is_valid=validation_result.is_valid,
                score=validation_result.score,
                has_project_name=validation_result.has_project_name,
                has_overview=validation_result.has_overview,
                has_tech_stack=validation_result.has_tech_stack,
                has_feature_count=validation_result.has_feature_count,
                has_core_features=validation_result.has_core_features,
                has_database_schema=validation_result.has_database_schema,
                has_api_endpoints=validation_result.has_api_endpoints,
                has_implementation_steps=validation_result.has_implementation_steps,
                has_success_criteria=validation_result.has_success_criteria,
                project_name=validation_result.project_name,
                feature_count=validation_result.feature_count,
                tech_stack=validation_result.tech_stack,
                missing_sections=validation_result.missing_sections,
                warnings=validation_result.warnings,
                errors=validation_result.errors,
            )

        return ImportSpecResponse(
            success=True,
            path=str(dest_path),
            validation=validation_response,
            message=f"Spec imported successfully to {dest_path}",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/upload/{project_name}", response_model=ImportSpecResponse)
async def upload_spec_file(
    project_name: str,
    file: UploadFile = File(...),
    validate: bool = True,
    spec_name: str = "main",
):
    """
    Upload a spec file to a project.

    Accepts file upload (drag-and-drop) and imports
    the spec into the project.
    """
    _init_imports()
    get_project_path = _get_registry_functions()

    # Validate project
    project_dir = get_project_path(project_name)
    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory no longer exists: {project_dir}"
        )

    # Check if agent is running
    lock_file = project_dir / ".agent.lock"
    if lock_file.exists():
        raise HTTPException(
            status_code=409,
            detail="Cannot upload spec while agent is running. Stop the agent first."
        )

    # Read file content
    try:
        content = await file.read()
        spec_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be a valid UTF-8 text file"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read file: {str(e)}"
        )

    # Import the content
    try:
        dest_path, validation_result = _import_spec_content(
            project_dir=project_dir,
            content=spec_content,
            validate=validate,
            spec_name=spec_name,
        )

        validation_response = None
        if validation_result:
            validation_response = ValidateSpecResponse(
                is_valid=validation_result.is_valid,
                score=validation_result.score,
                has_project_name=validation_result.has_project_name,
                has_overview=validation_result.has_overview,
                has_tech_stack=validation_result.has_tech_stack,
                has_feature_count=validation_result.has_feature_count,
                has_core_features=validation_result.has_core_features,
                has_database_schema=validation_result.has_database_schema,
                has_api_endpoints=validation_result.has_api_endpoints,
                has_implementation_steps=validation_result.has_implementation_steps,
                has_success_criteria=validation_result.has_success_criteria,
                project_name=validation_result.project_name,
                feature_count=validation_result.feature_count,
                tech_stack=validation_result.tech_stack,
                missing_sections=validation_result.missing_sections,
                warnings=validation_result.warnings,
                errors=validation_result.errors,
            )

        return ImportSpecResponse(
            success=True,
            path=str(dest_path),
            validation=validation_response,
            message=f"Spec file '{file.filename}' imported successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/refine", response_model=RefineSpecResponse)
async def refine_spec(request: RefineSpecRequest):
    """
    Refine a spec based on user feedback.

    Uses Claude to generate an improved version of the spec
    incorporating the user's feedback.
    """
    analyzer = _get_analyzer()

    try:
        refined_spec = await analyzer.suggest_refinements(
            spec_content=request.spec_content,
            user_feedback=request.feedback,
        )

        return RefineSpecResponse(
            success=True,
            refined_spec=refined_spec,
            message="Spec refined successfully",
        )
    except Exception as e:
        logger.error(f"Refinement failed: {e}")
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")


@router.get("/analysis/{project_name}")
async def get_project_analysis(project_name: str):
    """
    Get cached analysis result for a project.

    Returns the last analysis result if available,
    or null if no analysis has been performed.
    """
    from ..services.spec_analyzer import get_cached_analysis

    result = get_cached_analysis(project_name)
    if result:
        return result.to_dict()

    return {"cached": False, "message": "No cached analysis for this project"}


@router.delete("/analysis/{project_name}")
async def clear_project_analysis(project_name: str):
    """Clear cached analysis for a project."""
    from ..services.spec_analyzer import clear_analysis_cache

    clear_analysis_cache(project_name)
    return {"success": True, "message": f"Analysis cache cleared for {project_name}"}
