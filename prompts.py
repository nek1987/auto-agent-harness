"""
Prompt Loading Utilities
========================

Functions for loading prompt templates with project-specific support.

Fallback chain:
1. Project-specific: {project_dir}/prompts/{name}.md
2. Base template: .claude/templates/{name}.template.md

Multi-spec support:
- Projects can have multiple app specs (main, frontend, backend, etc.)
- Specs are tracked in {project_dir}/prompts/.spec_manifest.json
- Features are tagged with source_spec to track their origin

Skills integration (SDK 0.1.19):
- Skills from .claude/skills/ are loaded and injected into prompts
- {{SKILLS_CONTEXT}} placeholder is replaced with relevant skills
- Skills are selected based on agent mode (analysis, coding, frontend, etc.)

Spec Validation:
- validate_spec_structure() validates XML structure of app_spec.txt
- extract_spec_metadata() extracts project_name, feature_count, tech_stack
- get_spec_quality_score() returns quality score 0-100
"""

import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from lib.skills_loader import SkillsLoader, get_skills_context

# Base templates location (generic templates)
TEMPLATES_DIR = Path(__file__).parent / ".claude" / "templates"

# Harness directory (for loading skills from harness rather than project)
HARNESS_DIR = Path(__file__).parent

logger = logging.getLogger(__name__)


def get_project_prompts_dir(project_dir: Path) -> Path:
    """Get the prompts directory for a specific project."""
    return project_dir / "prompts"


def load_prompt(name: str, project_dir: Path | None = None, mode: str | None = None) -> str:
    """
    Load a prompt template with fallback chain and optional skills injection.

    Fallback order:
    1. Project-specific: {project_dir}/prompts/{name}.md
    2. Base template: .claude/templates/{name}.template.md

    If mode is provided, skills context will be injected:
    - {{SKILLS_CONTEXT}} placeholder is replaced with relevant skills
    - If no placeholder, skills are appended to the prompt

    Args:
        name: The prompt name (without extension), e.g., "initializer_prompt"
        project_dir: Optional project directory for project-specific prompts
        mode: Optional agent mode for skills injection (analysis, coding, frontend, etc.)

    Returns:
        The prompt content as a string, with skills injected if mode is provided

    Raises:
        FileNotFoundError: If prompt not found in any location
    """
    content = None

    # 1. Try project-specific first
    if project_dir:
        project_prompts = get_project_prompts_dir(project_dir)
        project_path = project_prompts / f"{name}.md"
        if project_path.exists():
            try:
                content = project_path.read_text(encoding="utf-8")
            except (OSError, PermissionError) as e:
                print(f"Warning: Could not read {project_path}: {e}")

    # 2. Try base template if not found
    if content is None:
        template_path = TEMPLATES_DIR / f"{name}.template.md"
        if template_path.exists():
            try:
                content = template_path.read_text(encoding="utf-8")
            except (OSError, PermissionError) as e:
                print(f"Warning: Could not read {template_path}: {e}")

    if content is None:
        raise FileNotFoundError(
            f"Prompt '{name}' not found in:\n"
            f"  - Project: {project_dir / 'prompts' if project_dir else 'N/A'}\n"
            f"  - Templates: {TEMPLATES_DIR}"
        )

    # Inject skills context if mode is provided
    if mode:
        content = inject_skills_context(content, mode)

    return content


def inject_skills_context(content: str, mode: str) -> str:
    """
    Inject skills context into a prompt.

    Loads skills from the harness .claude/skills/ directory and injects
    them into the prompt content.

    Args:
        content: The prompt content
        mode: Agent mode for selecting relevant skills

    Returns:
        Prompt with skills context injected
    """
    # Load skills from harness directory (not project directory)
    # Skills are shared across all projects
    skills_context = get_skills_context(HARNESS_DIR, mode)

    if not skills_context:
        # No skills found for this mode, remove placeholder if present
        return content.replace("{{SKILLS_CONTEXT}}", "")

    # Replace placeholder if present
    if "{{SKILLS_CONTEXT}}" in content:
        return content.replace("{{SKILLS_CONTEXT}}", skills_context)

    # Otherwise append skills section
    return content + f"\n\n## Available Expert Skills\n\n{skills_context}"


def get_skills_context_for_feature(
    assigned_skills: list[str] | None,
    skills_dir: Path | None = None,
) -> str:
    """
    Load skills context for a feature based on its assigned_skills.

    This function loads the SKILL.md content from each assigned skill
    and returns a combined context string that can be injected into
    the coding prompt to guide the agent's implementation.

    Args:
        assigned_skills: List of skill names assigned to the feature
        skills_dir: Optional path to skills directory. Defaults to harness skills.

    Returns:
        Combined skills context string, or empty string if no skills assigned
    """
    if not assigned_skills or len(assigned_skills) == 0:
        return ""

    if skills_dir is None:
        skills_dir = HARNESS_DIR / ".claude" / "skills"

    if not skills_dir.exists():
        return ""

    skills_context_parts = []

    for skill_name in assigned_skills:
        skill_path = skills_dir / skill_name
        skill_md_path = skill_path / "SKILL.md"

        if skill_md_path.exists():
            try:
                content = skill_md_path.read_text(encoding="utf-8")
                # Limit content to avoid overly long prompts
                # Take first 4000 characters which should capture key info
                if len(content) > 4000:
                    content = content[:4000] + "\n\n[... content truncated for brevity ...]"

                skills_context_parts.append(
                    f"### Skill: {skill_name}\n\n{content}"
                )
            except (OSError, PermissionError) as e:
                print(f"Warning: Could not read skill {skill_name}: {e}")
                continue

    if not skills_context_parts:
        return ""

    return (
        "## Assigned Expert Skills\n\n"
        "Apply the best practices, patterns, and guidelines from these skills:\n\n"
        + "\n\n---\n\n".join(skills_context_parts)
    )


def inject_feature_skills(content: str, assigned_skills: list[str] | None) -> str:
    """
    Inject feature-specific skills context into a prompt.

    This is used when the coding agent is working on a feature that has
    assigned skills from the Skills Analysis system.

    Args:
        content: The prompt content
        assigned_skills: List of skill names assigned to the feature

    Returns:
        Prompt with feature skills context injected
    """
    skills_context = get_skills_context_for_feature(assigned_skills)

    if not skills_context:
        # No feature skills, remove placeholder if present
        return content.replace("{{FEATURE_SKILLS}}", "")

    # Replace placeholder if present
    if "{{FEATURE_SKILLS}}" in content:
        return content.replace("{{FEATURE_SKILLS}}", skills_context)

    # Otherwise append skills section (before any existing skills section)
    if "## Available Expert Skills" in content:
        # Insert before the general skills section
        return content.replace(
            "## Available Expert Skills",
            f"{skills_context}\n\n## Available Expert Skills"
        )

    # Append at the end
    return content + f"\n\n{skills_context}"


def get_initializer_prompt(project_dir: Path | None = None) -> str:
    """Load the initializer prompt with skills context (project-specific if available)."""
    prompt = load_prompt("initializer_prompt", project_dir, mode="initializer")

    if project_dir and "[FEATURE_COUNT]" in prompt:
        try:
            spec_content = get_app_spec(project_dir)
            _, feature_count, _ = extract_spec_metadata(spec_content)
            if feature_count:
                prompt = prompt.replace("[FEATURE_COUNT]", str(feature_count))
            else:
                logger.warning("Initializer prompt still contains [FEATURE_COUNT] placeholder")
        except Exception as exc:
            logger.warning(f"Failed to auto-fill [FEATURE_COUNT] placeholder: {exc}")

    return prompt


def get_coding_prompt(project_dir: Path | None = None, use_docker: bool | None = None) -> str:
    """
    Load the coding agent prompt with skills context (project-specific if available).

    Args:
        project_dir: Optional project directory for project-specific prompts
        use_docker: Override Docker prompt selection. If None, auto-detect.

    Returns:
        The appropriate coding prompt (Docker or standard)
    """
    # Determine whether to use Docker prompt
    if use_docker is None and project_dir:
        use_docker = _should_use_docker_prompt(project_dir)

    if use_docker:
        # Try Docker prompt first, fall back to standard
        try:
            return load_prompt("coding_prompt_docker", project_dir, mode="coding")
        except FileNotFoundError:
            pass

    return load_prompt("coding_prompt", project_dir, mode="coding")


def _should_use_docker_prompt(project_dir: Path) -> bool:
    """
    Determine if project should use Docker-based prompts.

    Returns True if:
    - Project has docker-compose.yml, OR
    - Project uses Python/Go/Rust/Java (backend languages)
    """
    from lib.project_detector import should_use_docker_prompt

    return should_use_docker_prompt(project_dir)


def get_coding_prompt_yolo(project_dir: Path | None = None, use_docker: bool | None = None) -> str:
    """
    Load the YOLO mode coding agent prompt with skills context.

    In YOLO mode, browser testing is skipped but Docker workflow is still used
    for projects that benefit from container isolation.

    Args:
        project_dir: Optional project directory for project-specific prompts
        use_docker: Override Docker prompt selection. If None, auto-detect.

    Returns:
        The YOLO mode coding prompt
    """
    # For YOLO mode, we still use standard YOLO prompt
    # but it inherits Docker rules from project setup
    return load_prompt("coding_prompt_yolo", project_dir, mode="coding")


def get_analysis_prompt(project_dir: Path | None = None) -> str:
    """Load the analysis agent prompt with skills context (project-specific if available)."""
    return load_prompt("analysis_prompt", project_dir, mode="analysis")


def get_regression_prompt(project_dir: Path | None = None) -> str:
    """Load the regression prompt with skills context (project-specific if available)."""
    return load_prompt("regression_prompt", project_dir, mode="testing")


def get_redesign_prompt(project_dir: Path | None = None) -> str:
    """Load the redesign planner prompt with skills context (project-specific if available)."""
    return load_prompt("redesign_prompt", project_dir, mode="redesign")


def get_app_spec(project_dir: Path) -> str:
    """
    Load the app spec from the project.

    Checks in order:
    1. Project prompts directory: {project_dir}/prompts/app_spec.txt
    2. Project root (legacy): {project_dir}/app_spec.txt

    Args:
        project_dir: The project directory

    Returns:
        The app spec content

    Raises:
        FileNotFoundError: If no app_spec.txt found
    """
    # Try project prompts directory first
    project_prompts = get_project_prompts_dir(project_dir)
    spec_path = project_prompts / "app_spec.txt"
    if spec_path.exists():
        try:
            return spec_path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            raise FileNotFoundError(f"Could not read {spec_path}: {e}") from e

    # Fallback to legacy location in project root
    legacy_spec = project_dir / "app_spec.txt"
    if legacy_spec.exists():
        try:
            return legacy_spec.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            raise FileNotFoundError(f"Could not read {legacy_spec}: {e}") from e

    raise FileNotFoundError(f"No app_spec.txt found for project: {project_dir}")


def scaffold_project_prompts(project_dir: Path) -> Path:
    """
    Create the project prompts directory and copy base templates.

    This sets up a new project with template files that can be customized.

    Args:
        project_dir: The absolute path to the project directory

    Returns:
        The path to the project prompts directory
    """
    project_prompts = get_project_prompts_dir(project_dir)
    project_prompts.mkdir(parents=True, exist_ok=True)

    # Define template mappings: (source_template, destination_name)
    templates = [
        ("app_spec.template.txt", "app_spec.txt"),
        ("coding_prompt.template.md", "coding_prompt.md"),
        ("coding_prompt_yolo.template.md", "coding_prompt_yolo.md"),
        ("initializer_prompt.template.md", "initializer_prompt.md"),
    ]

    copied_files = []
    for template_name, dest_name in templates:
        template_path = TEMPLATES_DIR / template_name
        dest_path = project_prompts / dest_name

        # Only copy if template exists and destination doesn't
        if template_path.exists() and not dest_path.exists():
            try:
                shutil.copy(template_path, dest_path)
                copied_files.append(dest_name)
            except (OSError, PermissionError) as e:
                print(f"  Warning: Could not copy {dest_name}: {e}")

    if copied_files:
        print(f"  Created prompt files: {', '.join(copied_files)}")

    return project_prompts


def has_project_prompts(project_dir: Path) -> bool:
    """
    Check if a project has valid prompts set up.

    A project has valid prompts if:
    1. The prompts directory exists, AND
    2. app_spec.txt exists within it, AND
    3. app_spec.txt contains the <project_specification> tag

    Args:
        project_dir: The project directory to check

    Returns:
        True if valid project prompts exist, False otherwise
    """
    project_prompts = get_project_prompts_dir(project_dir)
    app_spec = project_prompts / "app_spec.txt"

    if not app_spec.exists():
        # Also check legacy location in project root
        legacy_spec = project_dir / "app_spec.txt"
        if legacy_spec.exists():
            try:
                content = legacy_spec.read_text(encoding="utf-8")
                return "<project_specification>" in content
            except (OSError, PermissionError):
                return False
        return False

    # Check for valid spec content
    try:
        content = app_spec.read_text(encoding="utf-8")
        return "<project_specification>" in content
    except (OSError, PermissionError):
        return False


def copy_spec_to_project(project_dir: Path) -> None:
    """
    Copy the app spec file into the project root directory for the agent to read.

    This maintains backwards compatibility - the agent expects app_spec.txt
    in the project root directory.

    The spec is sourced from: {project_dir}/prompts/app_spec.txt

    Args:
        project_dir: The project directory
    """
    spec_dest = project_dir / "app_spec.txt"

    # Don't overwrite if already exists
    if spec_dest.exists():
        return

    # Copy from project prompts directory
    project_prompts = get_project_prompts_dir(project_dir)
    project_spec = project_prompts / "app_spec.txt"
    if project_spec.exists():
        try:
            shutil.copy(project_spec, spec_dest)
            print("Copied app_spec.txt to project directory")
            return
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not copy app_spec.txt: {e}")
            return

    print("Warning: No app_spec.txt found to copy to project directory")


# ============================================================================
# Multi-Spec Support
# ============================================================================

SPEC_MANIFEST_FILE = ".spec_manifest.json"


def get_spec_manifest_path(project_dir: Path) -> Path:
    """Get the path to the spec manifest file."""
    return get_project_prompts_dir(project_dir) / SPEC_MANIFEST_FILE


def load_spec_manifest(project_dir: Path) -> dict:
    """
    Load the spec manifest for a project.

    Returns:
        Manifest dict with 'version' and 'specs' keys
    """
    manifest_path = get_spec_manifest_path(project_dir)

    if not manifest_path.exists():
        return {
            "version": "1.0",
            "specs": []
        }

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "version": "1.0",
            "specs": []
        }


def save_spec_manifest(project_dir: Path, manifest: dict) -> None:
    """Save the spec manifest for a project."""
    manifest_path = get_spec_manifest_path(project_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def register_spec(
    project_dir: Path,
    spec_name: str,
    spec_file: str,
    feature_count: int = 0,
    feature_id_start: Optional[int] = None,
    feature_id_end: Optional[int] = None,
    extends: Optional[str] = None,
) -> dict:
    """
    Register a new spec in the manifest.

    Args:
        project_dir: The project directory
        spec_name: Name for this spec (e.g., "main", "frontend")
        spec_file: Filename of the spec (e.g., "app_spec.txt", "app_spec_frontend.txt")
        feature_count: Number of features in this spec
        feature_id_start: First feature ID from this spec
        feature_id_end: Last feature ID from this spec
        extends: Name of spec this extends (optional)

    Returns:
        The updated manifest
    """
    manifest = load_spec_manifest(project_dir)

    # Check if spec already exists
    existing = next((s for s in manifest["specs"] if s["name"] == spec_name), None)

    spec_entry = {
        "name": spec_name,
        "file": spec_file,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_count": feature_count,
    }

    if feature_id_start is not None and feature_id_end is not None:
        spec_entry["feature_id_range"] = [feature_id_start, feature_id_end]

    if extends:
        spec_entry["extends"] = extends

    if existing:
        # Update existing
        idx = manifest["specs"].index(existing)
        manifest["specs"][idx] = spec_entry
    else:
        # Add new
        manifest["specs"].append(spec_entry)

    save_spec_manifest(project_dir, manifest)
    return manifest


def list_specs(project_dir: Path) -> list[dict]:
    """
    List all specs registered for a project.

    Returns:
        List of spec info dictionaries
    """
    manifest = load_spec_manifest(project_dir)
    return manifest.get("specs", [])


def get_spec_by_name(project_dir: Path, spec_name: str) -> Optional[dict]:
    """
    Get a spec by name.

    Args:
        project_dir: The project directory
        spec_name: Name of the spec to find

    Returns:
        Spec info dict or None if not found
    """
    specs = list_specs(project_dir)
    return next((s for s in specs if s["name"] == spec_name), None)


def get_all_app_specs(project_dir: Path) -> dict[str, str]:
    """
    Get all app specs from a project.

    Returns:
        Dict mapping spec name to content
    """
    project_prompts = get_project_prompts_dir(project_dir)
    result = {}

    # Get from manifest
    manifest = load_spec_manifest(project_dir)
    for spec in manifest.get("specs", []):
        spec_path = project_prompts / spec["file"]
        if spec_path.exists():
            try:
                result[spec["name"]] = spec_path.read_text(encoding="utf-8")
            except (OSError, PermissionError):
                continue

    # If no manifest, try default app_spec.txt
    if not result:
        try:
            result["main"] = get_app_spec(project_dir)
        except FileNotFoundError:
            pass

    return result


def add_spec_file(
    project_dir: Path,
    spec_name: str,
    content: str,
    extends: Optional[str] = None,
) -> Path:
    """
    Add a new spec file to a project.

    Args:
        project_dir: The project directory
        spec_name: Name for this spec (e.g., "frontend")
        content: The spec content
        extends: Name of spec this extends (optional)

    Returns:
        Path to the created spec file
    """
    project_prompts = get_project_prompts_dir(project_dir)
    project_prompts.mkdir(parents=True, exist_ok=True)

    # Generate filename
    if spec_name == "main":
        filename = "app_spec.txt"
    else:
        filename = f"app_spec_{spec_name}.txt"

    spec_path = project_prompts / filename
    spec_path.write_text(content, encoding="utf-8")

    # Register in manifest
    register_spec(
        project_dir=project_dir,
        spec_name=spec_name,
        spec_file=filename,
        extends=extends,
    )

    return spec_path


def update_spec_feature_range(
    project_dir: Path,
    spec_name: str,
    feature_count: int,
    feature_id_start: int,
    feature_id_end: int,
) -> None:
    """
    Update the feature range for a spec after features are created.

    Args:
        project_dir: The project directory
        spec_name: Name of the spec
        feature_count: Total features created from this spec
        feature_id_start: First feature ID
        feature_id_end: Last feature ID
    """
    manifest = load_spec_manifest(project_dir)

    for spec in manifest.get("specs", []):
        if spec["name"] == spec_name:
            spec["feature_count"] = feature_count
            spec["feature_id_range"] = [feature_id_start, feature_id_end]
            break

    save_spec_manifest(project_dir, manifest)


# ============================================================================
# Spec Validation
# ============================================================================

@dataclass
class SpecValidationResult:
    """Result of validating an app_spec.txt file."""

    is_valid: bool
    score: int  # 0-100

    # Presence of required sections
    has_project_name: bool = False
    has_overview: bool = False
    has_tech_stack: bool = False
    has_feature_count: bool = False
    has_core_features: bool = False
    has_database_schema: bool = False
    has_api_endpoints: bool = False
    has_implementation_steps: bool = False
    has_success_criteria: bool = False

    # Extracted data
    project_name: Optional[str] = None
    feature_count: Optional[int] = None
    tech_stack: Optional[dict] = None

    # Issues
    missing_sections: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "has_project_name": self.has_project_name,
            "has_overview": self.has_overview,
            "has_tech_stack": self.has_tech_stack,
            "has_feature_count": self.has_feature_count,
            "has_core_features": self.has_core_features,
            "has_database_schema": self.has_database_schema,
            "has_api_endpoints": self.has_api_endpoints,
            "has_implementation_steps": self.has_implementation_steps,
            "has_success_criteria": self.has_success_criteria,
            "project_name": self.project_name,
            "feature_count": self.feature_count,
            "tech_stack": self.tech_stack,
            "missing_sections": self.missing_sections,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# Section patterns for validation
REQUIRED_SECTIONS = {
    "project_specification": (r"<project_specification>", "Root <project_specification> tag"),
    "project_name": (r"<project_name>(.+?)</project_name>", "Project name"),
    "overview": (r"<overview>(.+?)</overview>", "Project overview"),
    "technology_stack": (r"<technology_stack>(.+?)</technology_stack>", "Technology stack"),
    "feature_count": (r"<feature_count>(\d+)</feature_count>", "Feature count"),
    "core_features": (r"<core_features>(.+?)</core_features>", "Core features"),
}

OPTIONAL_SECTIONS = {
    "database_schema": (r"<database_schema>(.+?)</database_schema>", "Database schema"),
    "api_endpoints": (r"<api_endpoints_summary>(.+?)</api_endpoints_summary>", "API endpoints"),
    "implementation_steps": (r"<implementation_steps>(.+?)</implementation_steps>", "Implementation steps"),
    "success_criteria": (r"<success_criteria>(.+?)</success_criteria>", "Success criteria"),
}


def validate_spec_structure(spec_content: str) -> SpecValidationResult:
    """
    Validate the XML structure of an app_spec.txt file.

    Checks for:
    - Required sections (project_specification, project_name, overview, tech_stack, etc.)
    - Optional sections (database_schema, api_endpoints, etc.)
    - Extracts metadata (project_name, feature_count, tech_stack)
    - Calculates quality score based on completeness

    Args:
        spec_content: The content of the app_spec.txt file

    Returns:
        SpecValidationResult with validation details
    """
    result = SpecValidationResult(is_valid=True, score=0)

    # Check for empty content
    if not spec_content or not spec_content.strip():
        result.is_valid = False
        result.errors.append("Spec content is empty")
        return result

    # Check required sections
    for section_name, (pattern, display_name) in REQUIRED_SECTIONS.items():
        match = re.search(pattern, spec_content, re.DOTALL | re.IGNORECASE)
        if match:
            setattr(result, f"has_{section_name}", True)
        else:
            result.missing_sections.append(display_name)
            if section_name == "project_specification":
                result.errors.append(f"Missing required: {display_name}")
                result.is_valid = False

    # Check optional sections
    for section_name, (pattern, display_name) in OPTIONAL_SECTIONS.items():
        match = re.search(pattern, spec_content, re.DOTALL | re.IGNORECASE)
        if match:
            setattr(result, f"has_{section_name}", True)
        else:
            result.warnings.append(f"Optional section missing: {display_name}")

    # Extract metadata
    result.project_name, result.feature_count, result.tech_stack = extract_spec_metadata(spec_content)

    # Validate extracted data
    if result.has_feature_count and result.feature_count is not None:
        if result.feature_count < 1:
            result.errors.append("Feature count must be at least 1")
            result.is_valid = False
        elif result.feature_count > 500:
            result.warnings.append(f"Very high feature count ({result.feature_count}) - may be unrealistic")

    # Check for minimum content length
    if len(spec_content.strip()) < 500:
        result.warnings.append("Spec content is very short - may lack detail")

    # Calculate quality score
    result.score = get_spec_quality_score(result)

    return result


def extract_spec_metadata(spec_content: str) -> tuple[Optional[str], Optional[int], Optional[dict]]:
    """
    Extract metadata from spec content.

    Args:
        spec_content: The content of the app_spec.txt file

    Returns:
        Tuple of (project_name, feature_count, tech_stack)
    """
    project_name = None
    feature_count = None
    tech_stack = None

    # Extract project name
    name_match = re.search(r"<project_name>(.+?)</project_name>", spec_content, re.DOTALL | re.IGNORECASE)
    if name_match:
        project_name = name_match.group(1).strip()

    # Extract feature count
    count_match = re.search(r"<feature_count>(\d+)</feature_count>", spec_content, re.IGNORECASE)
    if count_match:
        try:
            feature_count = int(count_match.group(1))
        except ValueError:
            pass

    # Extract technology stack
    tech_match = re.search(r"<technology_stack>(.+?)</technology_stack>", spec_content, re.DOTALL | re.IGNORECASE)
    if tech_match:
        tech_content = tech_match.group(1)
        tech_stack = {}

        # Try to extract frontend/backend
        frontend_match = re.search(r"<frontend>(.+?)</frontend>", tech_content, re.DOTALL | re.IGNORECASE)
        if frontend_match:
            tech_stack["frontend"] = frontend_match.group(1).strip()

        backend_match = re.search(r"<backend>(.+?)</backend>", tech_content, re.DOTALL | re.IGNORECASE)
        if backend_match:
            tech_stack["backend"] = backend_match.group(1).strip()

        database_match = re.search(r"<database>(.+?)</database>", tech_content, re.DOTALL | re.IGNORECASE)
        if database_match:
            tech_stack["database"] = database_match.group(1).strip()

    return project_name, feature_count, tech_stack


def get_spec_quality_score(result: SpecValidationResult) -> int:
    """
    Calculate quality score for a spec validation result.

    Scoring breakdown:
    - Required sections (60 points): 10 each
    - Optional sections (30 points): 7.5 each
    - No errors (10 points)

    Args:
        result: SpecValidationResult from validation

    Returns:
        Score from 0-100
    """
    score = 0

    # Required sections (10 points each, max 60)
    required_checks = [
        result.has_project_name,
        result.has_overview,
        result.has_tech_stack,
        result.has_feature_count,
        result.has_core_features,
        hasattr(result, 'has_project_specification') and getattr(result, 'has_project_specification', False),
    ]
    score += sum(10 for check in required_checks if check)

    # Optional sections (7.5 points each, max 30)
    optional_checks = [
        result.has_database_schema,
        result.has_api_endpoints,
        result.has_implementation_steps,
        result.has_success_criteria,
    ]
    score += sum(7.5 for check in optional_checks if check)

    # No errors bonus (10 points)
    if not result.errors:
        score += 10

    return min(100, int(score))


def import_spec_file(
    project_dir: Path,
    spec_path: Path,
    validate: bool = True,
    spec_name: str = "main",
) -> tuple[Path, Optional[SpecValidationResult]]:
    """
    Import an existing spec file into a project.

    Args:
        project_dir: The project directory
        spec_path: Path to the spec file to import
        validate: Whether to validate the spec before importing
        spec_name: Name for this spec in the manifest

    Returns:
        Tuple of (destination_path, validation_result or None)

    Raises:
        FileNotFoundError: If spec file doesn't exist
        ValueError: If validation fails and validate=True
    """
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    # Read the spec content
    content = spec_path.read_text(encoding="utf-8")

    # Validate if requested
    validation_result = None
    if validate:
        validation_result = validate_spec_structure(content)
        if not validation_result.is_valid:
            error_msg = "; ".join(validation_result.errors)
            raise ValueError(f"Spec validation failed: {error_msg}")

    # Create prompts directory
    project_prompts = get_project_prompts_dir(project_dir)
    project_prompts.mkdir(parents=True, exist_ok=True)

    # Determine destination filename
    if spec_name == "main":
        dest_filename = "app_spec.txt"
    else:
        dest_filename = f"app_spec_{spec_name}.txt"

    dest_path = project_prompts / dest_filename

    # Copy the spec file
    shutil.copy(spec_path, dest_path)

    # Register in manifest
    feature_count = validation_result.feature_count if validation_result else 0
    register_spec(
        project_dir=project_dir,
        spec_name=spec_name,
        spec_file=dest_filename,
        feature_count=feature_count or 0,
    )

    return dest_path, validation_result


def import_spec_content(
    project_dir: Path,
    content: str,
    validate: bool = True,
    spec_name: str = "main",
) -> tuple[Path, Optional[SpecValidationResult]]:
    """
    Import spec content directly into a project.

    Args:
        project_dir: The project directory
        content: The spec content to import
        validate: Whether to validate the spec before importing
        spec_name: Name for this spec in the manifest

    Returns:
        Tuple of (destination_path, validation_result or None)

    Raises:
        ValueError: If validation fails and validate=True
    """
    # Validate if requested
    validation_result = None
    if validate:
        validation_result = validate_spec_structure(content)
        if not validation_result.is_valid:
            error_msg = "; ".join(validation_result.errors)
            raise ValueError(f"Spec validation failed: {error_msg}")

    # Create prompts directory
    project_prompts = get_project_prompts_dir(project_dir)
    project_prompts.mkdir(parents=True, exist_ok=True)

    # Determine destination filename
    if spec_name == "main":
        dest_filename = "app_spec.txt"
    else:
        dest_filename = f"app_spec_{spec_name}.txt"

    dest_path = project_prompts / dest_filename

    # Write the spec content
    dest_path.write_text(content, encoding="utf-8")

    # Register in manifest
    feature_count = validation_result.feature_count if validation_result else 0
    register_spec(
        project_dir=project_dir,
        spec_name=spec_name,
        spec_file=dest_filename,
        feature_count=feature_count or 0,
    )

    return dest_path, validation_result
