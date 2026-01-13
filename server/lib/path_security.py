"""
Path Security Module
====================

Provides path validation to restrict file system access to allowed directories.
Prevents path traversal attacks and symlink escapes.
"""

import os
from pathlib import Path
from typing import Optional


class PathNotAllowedError(Exception):
    """Raised when a path is outside the allowed directory."""
    pass


class PathSecurityConfig:
    """Configuration for path security."""

    def __init__(self):
        self._allowed_root: Optional[Path] = None
        self._data_dir: Optional[Path] = None
        self._require_localhost: bool = True
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        allowed_root = os.getenv("ALLOWED_ROOT_DIRECTORY")
        if allowed_root:
            self._allowed_root = Path(allowed_root).resolve()

        data_dir = os.getenv("DATA_DIR")
        if data_dir:
            self._data_dir = Path(data_dir).resolve()
        else:
            self._data_dir = Path.home() / ".auto-agent-harness"

        self._require_localhost = os.getenv("REQUIRE_LOCALHOST", "true").lower() == "true"

    @property
    def allowed_root(self) -> Optional[Path]:
        """Get the allowed root directory."""
        return self._allowed_root

    @property
    def data_dir(self) -> Path:
        """Get the data directory (always allowed)."""
        return self._data_dir

    @property
    def require_localhost(self) -> bool:
        """Whether to require localhost connections."""
        return self._require_localhost


# Global configuration instance
config = PathSecurityConfig()


def is_path_allowed(path: Path, check_symlinks: bool = True) -> bool:
    """
    Check if a path is within the allowed directory.

    Args:
        path: The path to check (will be resolved to absolute)
        check_symlinks: Whether to validate symlink targets

    Returns:
        True if path is allowed, False otherwise
    """
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        return False

    # DATA_DIR is always allowed (for settings, users, etc.)
    if config.data_dir:
        try:
            resolved.relative_to(config.data_dir)
            return True
        except ValueError:
            pass

    # If no ALLOWED_ROOT_DIRECTORY is set, allow all paths
    if config.allowed_root is None:
        return True

    # Check if path is within allowed root
    try:
        resolved.relative_to(config.allowed_root)
    except ValueError:
        return False

    # Check symlink targets if enabled
    if check_symlinks and path.is_symlink():
        try:
            target = path.readlink()
            # Resolve relative symlink targets
            if not target.is_absolute():
                target = (path.parent / target).resolve()
            else:
                target = target.resolve()

            # Symlink target must also be allowed
            return is_path_allowed(target, check_symlinks=False)
        except (OSError, ValueError):
            return False

    return True


def validate_path(path: Path, check_symlinks: bool = True) -> Path:
    """
    Validate and return the resolved path.

    Args:
        path: The path to validate
        check_symlinks: Whether to validate symlink targets

    Returns:
        The resolved absolute path

    Raises:
        PathNotAllowedError: If path is outside allowed directory
    """
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError) as e:
        raise PathNotAllowedError(f"Invalid path: {path}") from e

    if not is_path_allowed(path, check_symlinks):
        if config.allowed_root:
            raise PathNotAllowedError(
                f"Path '{resolved}' is outside allowed directory '{config.allowed_root}'"
            )
        raise PathNotAllowedError(f"Path '{resolved}' is not allowed")

    return resolved


def validate_path_or_none(path: Path, check_symlinks: bool = True) -> Optional[Path]:
    """
    Validate path and return resolved path or None if not allowed.

    Args:
        path: The path to validate
        check_symlinks: Whether to validate symlink targets

    Returns:
        The resolved absolute path or None if not allowed
    """
    try:
        return validate_path(path, check_symlinks)
    except PathNotAllowedError:
        return None


def get_safe_relative_path(path: Path, base: Path) -> Optional[str]:
    """
    Get relative path if it's within the base directory.

    Args:
        path: The path to make relative
        base: The base directory

    Returns:
        Relative path string or None if not within base
    """
    try:
        resolved = Path(path).resolve()
        base_resolved = Path(base).resolve()
        return str(resolved.relative_to(base_resolved))
    except (ValueError, OSError):
        return None


def list_directory_safe(directory: Path) -> list[dict]:
    """
    Safely list directory contents with path validation.

    Args:
        directory: Directory to list

    Returns:
        List of file/directory info dicts

    Raises:
        PathNotAllowedError: If directory is outside allowed area
    """
    validated = validate_path(directory)

    if not validated.is_dir():
        raise PathNotAllowedError(f"'{directory}' is not a directory")

    items = []
    try:
        for item in sorted(validated.iterdir()):
            # Skip hidden files in listing
            if item.name.startswith("."):
                continue

            try:
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "is_file": item.is_file(),
                    "is_symlink": item.is_symlink(),
                    "size": stat.st_size if item.is_file() else None,
                })
            except (OSError, PermissionError):
                # Skip items we can't access
                continue
    except PermissionError:
        raise PathNotAllowedError(f"Permission denied: '{directory}'")

    return items


def read_file_safe(file_path: Path, max_size: int = 10 * 1024 * 1024) -> str:
    """
    Safely read file contents with path validation.

    Args:
        file_path: File to read
        max_size: Maximum file size in bytes (default 10MB)

    Returns:
        File contents as string

    Raises:
        PathNotAllowedError: If file is outside allowed area
        ValueError: If file is too large
    """
    validated = validate_path(file_path)

    if not validated.is_file():
        raise PathNotAllowedError(f"'{file_path}' is not a file")

    size = validated.stat().st_size
    if size > max_size:
        raise ValueError(f"File too large: {size} bytes (max {max_size})")

    return validated.read_text()


def write_file_safe(file_path: Path, content: str) -> None:
    """
    Safely write file contents with path validation.

    Args:
        file_path: File to write
        content: Content to write

    Raises:
        PathNotAllowedError: If file is outside allowed area
    """
    validated = validate_path(file_path)

    # Ensure parent directory exists
    validated.parent.mkdir(parents=True, exist_ok=True)

    validated.write_text(content)
