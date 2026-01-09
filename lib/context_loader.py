"""
Context Files Loader
====================

Loads context files from project directories to include in agent prompts.
Context files provide project-specific rules, conventions, and guidelines.

Directory structure:
    {project_dir}/.context/
    ├── CLAUDE.md           # Main project rules
    ├── CODE_QUALITY.md     # Code standards
    ├── SECURITY.md         # Security guidelines
    └── context-metadata.json  # Optional: file descriptions and priorities
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ContextFile:
    """Represents a context file with metadata."""
    path: Path
    name: str
    content: str
    priority: int = 100  # Lower = loaded first
    description: str = ""
    condition: Optional[str] = None  # e.g., "mode == 'coding'"

    @property
    def formatted(self) -> str:
        """Format the context file for inclusion in prompts."""
        header = f"# Context: {self.name}"
        if self.description:
            header += f"\n# {self.description}"
        return f"{header}\n\n{self.content}"


@dataclass
class ContextMetadata:
    """Metadata for context files in a project."""
    files: dict[str, dict] = field(default_factory=dict)
    default_priority: int = 100

    @classmethod
    def load(cls, metadata_path: Path) -> "ContextMetadata":
        """Load metadata from JSON file."""
        if not metadata_path.exists():
            return cls()

        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            return cls(
                files=data.get("files", {}),
                default_priority=data.get("default_priority", 100),
            )
        except (json.JSONDecodeError, OSError):
            return cls()

    def get_priority(self, filename: str) -> int:
        """Get priority for a file (lower = higher priority)."""
        if filename in self.files:
            return self.files[filename].get("priority", self.default_priority)
        return self.default_priority

    def get_description(self, filename: str) -> str:
        """Get description for a file."""
        if filename in self.files:
            return self.files[filename].get("description", "")
        return ""

    def get_condition(self, filename: str) -> Optional[str]:
        """Get condition for when to include a file."""
        if filename in self.files:
            return self.files[filename].get("condition")
        return None


def get_context_dir(project_dir: Path) -> Path:
    """Get the context directory for a project."""
    return project_dir / ".context"


def get_context_files(
    project_dir: Path,
    mode: Optional[str] = None,
) -> list[ContextFile]:
    """
    Get all context files from a project directory.

    Args:
        project_dir: The project directory
        mode: Optional mode to filter files by condition (e.g., "coding", "initializer")

    Returns:
        List of ContextFile objects sorted by priority
    """
    context_dir = get_context_dir(project_dir)

    if not context_dir.exists():
        return []

    # Load metadata
    metadata_path = context_dir / "context-metadata.json"
    metadata = ContextMetadata.load(metadata_path)

    context_files = []

    # Find all markdown files
    for file_path in context_dir.glob("*.md"):
        if file_path.name.startswith("."):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, PermissionError):
            continue

        # Get metadata for this file
        priority = metadata.get_priority(file_path.name)
        description = metadata.get_description(file_path.name)
        condition = metadata.get_condition(file_path.name)

        # Check condition
        if condition and mode:
            # Simple condition evaluation
            if not _evaluate_condition(condition, {"mode": mode}):
                continue

        context_files.append(ContextFile(
            path=file_path,
            name=file_path.stem,
            content=content.strip(),
            priority=priority,
            description=description,
            condition=condition,
        ))

    # Sort by priority (lower first)
    context_files.sort(key=lambda f: f.priority)

    return context_files


def _evaluate_condition(condition: str, variables: dict) -> bool:
    """
    Evaluate a simple condition string.

    Supports:
    - mode == 'coding'
    - mode != 'initializer'
    - mode in ['coding', 'testing']

    Args:
        condition: The condition string
        variables: Dictionary of variable values

    Returns:
        True if condition is met
    """
    try:
        # Simple equality check
        if "==" in condition:
            parts = condition.split("==")
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected = parts[1].strip().strip("'\"")
                return variables.get(var_name) == expected

        # Inequality check
        if "!=" in condition:
            parts = condition.split("!=")
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected = parts[1].strip().strip("'\"")
                return variables.get(var_name) != expected

        # 'in' check
        if " in " in condition:
            parts = condition.split(" in ")
            if len(parts) == 2:
                var_name = parts[0].strip()
                # Parse list
                list_str = parts[1].strip()
                if list_str.startswith("[") and list_str.endswith("]"):
                    items = [
                        item.strip().strip("'\"")
                        for item in list_str[1:-1].split(",")
                    ]
                    return variables.get(var_name) in items

    except Exception:
        pass

    # Default to True if condition cannot be evaluated
    return True


def load_context_files(
    project_dir: Path,
    mode: Optional[str] = None,
    separator: str = "\n\n---\n\n",
) -> str:
    """
    Load and concatenate all context files into a single string.

    Args:
        project_dir: The project directory
        mode: Optional mode to filter files
        separator: String to separate context files

    Returns:
        Combined context string ready for prompt inclusion
    """
    files = get_context_files(project_dir, mode)

    if not files:
        return ""

    return separator.join(f.formatted for f in files)


def create_context_dir(project_dir: Path) -> Path:
    """
    Create the context directory with default files.

    Args:
        project_dir: The project directory

    Returns:
        Path to the created context directory
    """
    context_dir = get_context_dir(project_dir)
    context_dir.mkdir(parents=True, exist_ok=True)

    # Create default CLAUDE.md
    claude_md = context_dir / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text("""# Project Rules

Add project-specific rules and conventions here.

## Code Style

- Follow existing patterns in the codebase
- Use TypeScript/Python type hints
- Write tests for new features

## Architecture

- Describe your project architecture here

## Conventions

- Add naming conventions
- Add file organization rules
""", encoding="utf-8")

    # Create metadata file
    metadata_path = context_dir / "context-metadata.json"
    if not metadata_path.exists():
        metadata = {
            "default_priority": 100,
            "files": {
                "CLAUDE.md": {
                    "priority": 10,
                    "description": "Main project rules and conventions"
                }
            }
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return context_dir


def list_available_context_files(project_dir: Path) -> list[dict]:
    """
    List all available context files with their metadata.

    Args:
        project_dir: The project directory

    Returns:
        List of file info dictionaries
    """
    context_dir = get_context_dir(project_dir)

    if not context_dir.exists():
        return []

    metadata_path = context_dir / "context-metadata.json"
    metadata = ContextMetadata.load(metadata_path)

    result = []
    for file_path in context_dir.glob("*.md"):
        if file_path.name.startswith("."):
            continue

        result.append({
            "name": file_path.name,
            "path": str(file_path),
            "priority": metadata.get_priority(file_path.name),
            "description": metadata.get_description(file_path.name),
            "condition": metadata.get_condition(file_path.name),
            "size": file_path.stat().st_size,
        })

    return sorted(result, key=lambda x: x["priority"])
