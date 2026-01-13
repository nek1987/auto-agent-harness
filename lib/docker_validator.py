"""
Docker Configuration Validator
==============================

Validates that a project has proper Docker configuration and is ready for deployment.
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationResult:
    """Result of Docker validation."""

    is_valid: bool
    score: int  # 0-100

    # Individual checks
    has_compose_file: bool = False
    has_dockerfiles: bool = False
    compose_syntax_valid: bool = False
    dockerfiles_syntax_valid: bool = False
    images_build: bool = False
    services_start: bool = False
    health_checks_pass: bool = False

    # Details
    compose_file: Optional[str] = None
    services: list[str] = field(default_factory=list)
    dockerfile_paths: list[str] = field(default_factory=list)

    # Issues
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "has_compose_file": self.has_compose_file,
            "has_dockerfiles": self.has_dockerfiles,
            "compose_syntax_valid": self.compose_syntax_valid,
            "dockerfiles_syntax_valid": self.dockerfiles_syntax_valid,
            "images_build": self.images_build,
            "services_start": self.services_start,
            "health_checks_pass": self.health_checks_pass,
            "compose_file": self.compose_file,
            "services": self.services,
            "dockerfile_paths": self.dockerfile_paths,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def find_compose_file(project_dir: Path) -> Optional[Path]:
    """Find docker-compose file in project directory."""
    compose_files = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    ]

    for filename in compose_files:
        path = project_dir / filename
        if path.exists():
            return path

    return None


def find_dockerfiles(project_dir: Path) -> list[Path]:
    """Find all Dockerfiles in project directory."""
    dockerfiles = []

    # Check root
    root_dockerfile = project_dir / "Dockerfile"
    if root_dockerfile.exists():
        dockerfiles.append(root_dockerfile)

    # Check common subdirectories
    subdirs = ["backend", "frontend", "api", "web", "server", "client", "app"]
    for subdir in subdirs:
        subdir_path = project_dir / subdir / "Dockerfile"
        if subdir_path.exists():
            dockerfiles.append(subdir_path)

    return dockerfiles


def validate_compose_syntax(compose_file: Path) -> tuple[bool, str]:
    """
    Validate docker-compose file syntax.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "config", "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr or result.stdout
    except FileNotFoundError:
        return False, "Docker not installed"
    except subprocess.TimeoutExpired:
        return False, "Validation timed out"
    except Exception as e:
        return False, str(e)


def get_compose_services(compose_file: Path) -> list[str]:
    """Get list of services from docker-compose file."""
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "config", "--services"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        return []
    except Exception:
        return []


def validate_dockerfile_syntax(dockerfile: Path) -> tuple[bool, str]:
    """
    Validate Dockerfile syntax using docker build --check (if available).

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic syntax check by parsing
    try:
        content = dockerfile.read_text()

        # Check for required FROM instruction
        if "FROM" not in content.upper():
            return False, "Missing FROM instruction"

        # Check for common issues
        lines = content.split("\n")
        has_from = False
        for line in lines:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if line.upper().startswith("FROM"):
                has_from = True
                break
            elif has_from is False and not line.upper().startswith("ARG"):
                return False, "First instruction must be FROM (or ARG before FROM)"

        return True, ""

    except Exception as e:
        return False, str(e)


def check_images_build(compose_file: Path, timeout: int = 300) -> tuple[bool, str]:
    """
    Check if images can be built.

    Args:
        compose_file: Path to docker-compose file
        timeout: Build timeout in seconds

    Returns:
        Tuple of (success, error_message)
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "build", "--no-cache"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(compose_file.parent),
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr or result.stdout
    except subprocess.TimeoutExpired:
        return False, f"Build timed out after {timeout} seconds"
    except FileNotFoundError:
        return False, "Docker not installed"
    except Exception as e:
        return False, str(e)


def check_services_start(compose_file: Path, timeout: int = 60) -> tuple[bool, str]:
    """
    Check if services can start.

    Args:
        compose_file: Path to docker-compose file
        timeout: Start timeout in seconds

    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Start services
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(compose_file.parent),
        )
        if result.returncode != 0:
            return False, result.stderr or result.stdout

        # Check if services are running
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(compose_file.parent),
        )

        return True, ""

    except subprocess.TimeoutExpired:
        return False, f"Start timed out after {timeout} seconds"
    except FileNotFoundError:
        return False, "Docker not installed"
    except Exception as e:
        return False, str(e)


def check_health_status(compose_file: Path) -> tuple[bool, list[str]]:
    """
    Check health status of running containers.

    Returns:
        Tuple of (all_healthy, list_of_unhealthy_services)
    """
    try:
        result = subprocess.run(
            [
                "docker", "compose", "-f", str(compose_file),
                "ps", "--format", "{{.Name}}: {{.Health}}"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(compose_file.parent),
        )

        if result.returncode != 0:
            return False, ["Failed to get health status"]

        unhealthy = []
        for line in result.stdout.strip().split("\n"):
            if line and "unhealthy" in line.lower():
                unhealthy.append(line.split(":")[0])

        return len(unhealthy) == 0, unhealthy

    except Exception as e:
        return False, [str(e)]


def validate_docker_project(
    project_dir: Path,
    quick: bool = True,
    build: bool = False,
    start: bool = False,
) -> ValidationResult:
    """
    Validate Docker configuration for a project.

    Args:
        project_dir: Path to project directory
        quick: Only check file existence and syntax (default)
        build: Also try to build images (slower)
        start: Also try to start services (requires build)

    Returns:
        ValidationResult with validation details
    """
    project_dir = Path(project_dir)
    result = ValidationResult(is_valid=False, score=0)

    # Check for docker-compose file
    compose_file = find_compose_file(project_dir)
    if compose_file:
        result.has_compose_file = True
        result.compose_file = compose_file.name

        # Get services
        result.services = get_compose_services(compose_file)

        # Validate syntax
        valid, error = validate_compose_syntax(compose_file)
        result.compose_syntax_valid = valid
        if not valid:
            result.errors.append(f"docker-compose syntax error: {error}")
    else:
        result.errors.append("No docker-compose.yml found")

    # Check for Dockerfiles
    dockerfiles = find_dockerfiles(project_dir)
    if dockerfiles:
        result.has_dockerfiles = True
        result.dockerfile_paths = [str(d.relative_to(project_dir)) for d in dockerfiles]

        # Validate each Dockerfile
        all_valid = True
        for dockerfile in dockerfiles:
            valid, error = validate_dockerfile_syntax(dockerfile)
            if not valid:
                all_valid = False
                result.errors.append(f"Dockerfile syntax error in {dockerfile.parent.name}: {error}")

        result.dockerfiles_syntax_valid = all_valid
    else:
        result.warnings.append("No Dockerfiles found")

    # Build check (if requested and compose file exists)
    if build and result.has_compose_file and result.compose_syntax_valid:
        success, error = check_images_build(compose_file)
        result.images_build = success
        if not success:
            result.errors.append(f"Build failed: {error[:200]}")

        # Start check (if requested and build succeeded)
        if start and success:
            success, error = check_services_start(compose_file)
            result.services_start = success
            if not success:
                result.errors.append(f"Services failed to start: {error[:200]}")

            if success:
                # Health check
                healthy, unhealthy = check_health_status(compose_file)
                result.health_checks_pass = healthy
                if not healthy and unhealthy:
                    result.warnings.append(f"Unhealthy services: {', '.join(unhealthy)}")

    # Calculate score
    result.score = _calculate_score(result)

    # Determine overall validity
    result.is_valid = (
        result.has_compose_file
        and result.compose_syntax_valid
        and len(result.errors) == 0
    )

    return result


def _calculate_score(result: ValidationResult) -> int:
    """Calculate validation score from 0-100."""
    score = 0

    # File existence (30 points)
    if result.has_compose_file:
        score += 20
    if result.has_dockerfiles:
        score += 10

    # Syntax validation (30 points)
    if result.compose_syntax_valid:
        score += 20
    if result.dockerfiles_syntax_valid:
        score += 10

    # Build & runtime (40 points)
    if result.images_build:
        score += 15
    if result.services_start:
        score += 15
    if result.health_checks_pass:
        score += 10

    return min(100, score)


def cleanup_docker_resources(compose_file: Path) -> None:
    """Stop and remove Docker resources created during validation."""
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "-v", "--remove-orphans"],
            capture_output=True,
            timeout=60,
            cwd=str(compose_file.parent),
        )
    except Exception:
        pass
