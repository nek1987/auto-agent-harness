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
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lib.skills_loader import SkillsLoader, get_skills_context

# Base templates location (generic templates)
TEMPLATES_DIR = Path(__file__).parent / ".claude" / "templates"

# Harness directory (for loading skills from harness rather than project)
HARNESS_DIR = Path(__file__).parent


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


def get_initializer_prompt(project_dir: Path | None = None) -> str:
    """Load the initializer prompt with skills context (project-specific if available)."""
    return load_prompt("initializer_prompt", project_dir, mode="initializer")


def get_coding_prompt(project_dir: Path | None = None) -> str:
    """Load the coding agent prompt with skills context (project-specific if available)."""
    return load_prompt("coding_prompt", project_dir, mode="coding")


def get_coding_prompt_yolo(project_dir: Path | None = None) -> str:
    """Load the YOLO mode coding agent prompt with skills context (project-specific if available)."""
    return load_prompt("coding_prompt_yolo", project_dir, mode="coding")


def get_analysis_prompt(project_dir: Path | None = None) -> str:
    """Load the analysis agent prompt with skills context (project-specific if available)."""
    return load_prompt("analysis_prompt", project_dir, mode="analysis")


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
