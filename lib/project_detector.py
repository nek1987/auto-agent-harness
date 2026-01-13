"""
Project Type Detector
=====================

Auto-detects project type based on files present in the project directory.
Used to select appropriate Docker templates and prompts.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ProjectTypeInfo:
    """Information about detected project type."""

    primary_type: str  # "python", "node", "go", "rust", "java", "ruby", "php", "unknown"
    secondary_type: Optional[str] = None  # For fullstack: e.g., "node" frontend
    framework: Optional[str] = None  # e.g., "fastapi", "nextjs", "gin"
    has_docker: bool = False
    has_database: bool = False
    database_type: Optional[str] = None  # "postgres", "mysql", "mongodb", "sqlite"

    @property
    def is_fullstack(self) -> bool:
        """Check if project has both frontend and backend."""
        return self.secondary_type is not None

    def __str__(self) -> str:
        if self.is_fullstack:
            return f"{self.primary_type}+{self.secondary_type}"
        return self.primary_type


# File indicators for each language/framework
LANGUAGE_INDICATORS = {
    "python": {
        "files": [
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock",
            "pdm.lock",
        ],
        "dirs": ["venv", ".venv", "__pycache__"],
    },
    "node": {
        "files": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"],
        "dirs": ["node_modules"],
    },
    "go": {
        "files": ["go.mod", "go.sum"],
        "dirs": [],
    },
    "rust": {
        "files": ["Cargo.toml", "Cargo.lock"],
        "dirs": ["target"],
    },
    "java": {
        "files": ["pom.xml", "build.gradle", "build.gradle.kts", "gradlew"],
        "dirs": ["src/main/java", ".gradle"],
    },
    "ruby": {
        "files": ["Gemfile", "Gemfile.lock", "Rakefile"],
        "dirs": [".bundle"],
    },
    "php": {
        "files": ["composer.json", "composer.lock", "artisan"],
        "dirs": ["vendor"],
    },
}

# Framework detection patterns (checked after language detection)
FRAMEWORK_PATTERNS = {
    "python": {
        "fastapi": ["main.py", "app/main.py"],  # + check for "fastapi" in requirements
        "django": ["manage.py", "settings.py"],
        "flask": [],  # Check for "flask" in requirements
        "streamlit": [],  # Check for "streamlit" in requirements
    },
    "node": {
        "nextjs": ["next.config.js", "next.config.mjs", "next.config.ts"],
        "nuxt": ["nuxt.config.js", "nuxt.config.ts"],
        "express": [],  # Check package.json
        "nestjs": ["nest-cli.json"],
        "vite": ["vite.config.js", "vite.config.ts"],
    },
    "go": {
        "gin": [],  # Check go.mod for gin-gonic
        "echo": [],  # Check go.mod for echo
        "fiber": [],  # Check go.mod for fiber
    },
    "rust": {
        "actix": [],  # Check Cargo.toml
        "axum": [],  # Check Cargo.toml
        "rocket": [],  # Check Cargo.toml
    },
}

# Database indicators
DATABASE_INDICATORS = {
    "postgres": {
        "files": [],
        "env_keys": ["DATABASE_URL", "POSTGRES_", "PG_"],
        "deps_python": ["asyncpg", "psycopg2", "psycopg"],
        "deps_node": ["pg", "postgres", "@prisma/client"],
    },
    "mysql": {
        "files": [],
        "env_keys": ["MYSQL_"],
        "deps_python": ["mysqlclient", "pymysql", "aiomysql"],
        "deps_node": ["mysql2", "mysql"],
    },
    "mongodb": {
        "files": [],
        "env_keys": ["MONGO_", "MONGODB_"],
        "deps_python": ["pymongo", "motor"],
        "deps_node": ["mongoose", "mongodb"],
    },
    "sqlite": {
        "files": ["*.db", "*.sqlite", "*.sqlite3"],
        "env_keys": [],
        "deps_python": ["aiosqlite"],
        "deps_node": ["better-sqlite3", "sqlite3"],
    },
    "redis": {
        "files": [],
        "env_keys": ["REDIS_"],
        "deps_python": ["redis", "aioredis"],
        "deps_node": ["redis", "ioredis"],
    },
}


def detect_language(project_dir: Path) -> list[str]:
    """
    Detect programming languages used in the project.

    Returns:
        List of detected languages (e.g., ["python", "node"] for fullstack)
    """
    detected = []

    for lang, indicators in LANGUAGE_INDICATORS.items():
        # Check files
        for filename in indicators["files"]:
            if (project_dir / filename).exists():
                if lang not in detected:
                    detected.append(lang)
                break

        # Check directories
        if lang not in detected:
            for dirname in indicators["dirs"]:
                if (project_dir / dirname).is_dir():
                    detected.append(lang)
                    break

    # Also check subdirectories (backend/, frontend/, etc.)
    for subdir in ["backend", "api", "server"]:
        subdir_path = project_dir / subdir
        if subdir_path.is_dir():
            sub_langs = detect_language(subdir_path)
            for lang in sub_langs:
                if lang not in detected:
                    detected.append(lang)

    for subdir in ["frontend", "web", "client", "ui"]:
        subdir_path = project_dir / subdir
        if subdir_path.is_dir():
            sub_langs = detect_language(subdir_path)
            for lang in sub_langs:
                if lang not in detected:
                    detected.append(lang)

    return detected


def detect_framework(project_dir: Path, language: str) -> Optional[str]:
    """
    Detect framework used for a specific language.

    Args:
        project_dir: Project directory
        language: Detected language

    Returns:
        Framework name or None
    """
    if language not in FRAMEWORK_PATTERNS:
        return None

    frameworks = FRAMEWORK_PATTERNS[language]

    for framework, patterns in frameworks.items():
        for pattern in patterns:
            if (project_dir / pattern).exists():
                return framework

    # Check dependency files for framework detection
    if language == "python":
        req_files = ["requirements.txt", "pyproject.toml", "Pipfile"]
        for req_file in req_files:
            req_path = project_dir / req_file
            if req_path.exists():
                try:
                    content = req_path.read_text().lower()
                    if "fastapi" in content:
                        return "fastapi"
                    if "django" in content:
                        return "django"
                    if "flask" in content:
                        return "flask"
                    if "streamlit" in content:
                        return "streamlit"
                except Exception:
                    pass

    elif language == "node":
        pkg_path = project_dir / "package.json"
        if pkg_path.exists():
            try:
                import json

                pkg = json.loads(pkg_path.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "next" in deps:
                    return "nextjs"
                if "nuxt" in deps:
                    return "nuxt"
                if "@nestjs/core" in deps:
                    return "nestjs"
                if "express" in deps:
                    return "express"
                if "vite" in deps:
                    return "vite"
            except Exception:
                pass

    return None


def detect_database(project_dir: Path, languages: list[str]) -> tuple[bool, Optional[str]]:
    """
    Detect if project uses a database and which type.

    Returns:
        Tuple of (has_database, database_type)
    """
    # Check docker-compose for database services
    compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
    for compose_file in compose_files:
        compose_path = project_dir / compose_file
        if compose_path.exists():
            try:
                content = compose_path.read_text().lower()
                if "postgres" in content:
                    return True, "postgres"
                if "mysql" in content or "mariadb" in content:
                    return True, "mysql"
                if "mongo" in content:
                    return True, "mongodb"
                if "redis" in content:
                    return True, "redis"
            except Exception:
                pass

    # Check .env files
    env_files = [".env", ".env.local", ".env.development"]
    for env_file in env_files:
        env_path = project_dir / env_file
        if env_path.exists():
            try:
                content = env_path.read_text().upper()
                for db_type, indicators in DATABASE_INDICATORS.items():
                    for key in indicators.get("env_keys", []):
                        if key in content:
                            return True, db_type
            except Exception:
                pass

    # Check dependency files
    if "python" in languages:
        req_files = ["requirements.txt", "pyproject.toml"]
        for req_file in req_files:
            req_path = project_dir / req_file
            if req_path.exists():
                try:
                    content = req_path.read_text().lower()
                    for db_type, indicators in DATABASE_INDICATORS.items():
                        for dep in indicators.get("deps_python", []):
                            if dep in content:
                                return True, db_type
                except Exception:
                    pass

    if "node" in languages:
        pkg_path = project_dir / "package.json"
        if pkg_path.exists():
            try:
                import json

                pkg = json.loads(pkg_path.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                for db_type, indicators in DATABASE_INDICATORS.items():
                    for dep in indicators.get("deps_node", []):
                        if dep in deps:
                            return True, db_type
            except Exception:
                pass

    return False, None


def has_docker_config(project_dir: Path) -> bool:
    """Check if project has Docker configuration."""
    docker_files = [
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    ]

    for docker_file in docker_files:
        if (project_dir / docker_file).exists():
            return True

    # Check subdirectories
    for subdir in ["backend", "frontend", "api", "web"]:
        if (project_dir / subdir / "Dockerfile").exists():
            return True

    return False


def detect_project_type(project_dir: Path) -> ProjectTypeInfo:
    """
    Detect project type from files in the directory.

    Args:
        project_dir: Path to the project directory

    Returns:
        ProjectTypeInfo with detected type information
    """
    project_dir = Path(project_dir)

    if not project_dir.exists():
        return ProjectTypeInfo(primary_type="unknown")

    # Detect languages
    languages = detect_language(project_dir)

    if not languages:
        return ProjectTypeInfo(
            primary_type="unknown",
            has_docker=has_docker_config(project_dir),
        )

    # Determine primary and secondary types
    primary_type = languages[0]
    secondary_type = languages[1] if len(languages) > 1 else None

    # For fullstack projects, prioritize backend language as primary
    backend_langs = {"python", "go", "rust", "java", "ruby", "php"}
    frontend_langs = {"node"}

    if len(languages) >= 2:
        # If we have both backend and frontend langs, make backend primary
        backend_found = [l for l in languages if l in backend_langs]
        frontend_found = [l for l in languages if l in frontend_langs]

        if backend_found and frontend_found:
            primary_type = backend_found[0]
            secondary_type = frontend_found[0]

    # Detect framework
    framework = detect_framework(project_dir, primary_type)

    # Also check subdirectories for framework
    if not framework:
        for subdir in ["backend", "api", "server"]:
            if (project_dir / subdir).is_dir():
                framework = detect_framework(project_dir / subdir, primary_type)
                if framework:
                    break

    # Detect database
    has_db, db_type = detect_database(project_dir, languages)

    # Check for Docker
    has_docker = has_docker_config(project_dir)

    return ProjectTypeInfo(
        primary_type=primary_type,
        secondary_type=secondary_type,
        framework=framework,
        has_docker=has_docker,
        has_database=has_db,
        database_type=db_type,
    )


def get_project_type_string(project_dir: Path) -> str:
    """
    Get a simple string representation of project type.

    Returns: "python", "node", "go", "fullstack", "unknown", etc.
    """
    info = detect_project_type(project_dir)

    if info.is_fullstack:
        return "fullstack"

    return info.primary_type


def should_use_docker_prompt(project_dir: Path) -> bool:
    """
    Determine if project should use Docker-based prompts.

    Returns True if:
    - Project already has Docker configuration, OR
    - Project uses Python/Go/Rust/Java (backend languages that benefit from containers)

    Returns False if:
    - Project is Node.js only (can run locally easily)
    - Project type is unknown
    """
    info = detect_project_type(project_dir)

    # Always use Docker if already configured
    if info.has_docker:
        return True

    # Backend languages benefit from Docker isolation
    docker_preferred_langs = {"python", "go", "rust", "java", "ruby", "php"}

    if info.primary_type in docker_preferred_langs:
        return True

    # Fullstack projects should use Docker
    if info.is_fullstack:
        return True

    return False
