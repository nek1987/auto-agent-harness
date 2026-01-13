"""
Project Scaffolding
===================

Create initial Docker configuration for projects based on detected type.
"""

from pathlib import Path
from typing import Optional

from lib.project_detector import ProjectTypeInfo, detect_project_type


# =============================================================================
# Docker Compose Templates
# =============================================================================

DOCKER_COMPOSE_PYTHON_FASTAPI = """services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "6100:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://app:app@db:5432/app
      - SECRET_KEY=dev-secret-key-change-in-production
    depends_on:
      db:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
"""

DOCKER_COMPOSE_PYTHON_DJANGO = """services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "6100:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://app:app@db:5432/app
      - SECRET_KEY=dev-secret-key-change-in-production
      - DEBUG=True
    depends_on:
      db:
        condition: service_healthy
    command: python manage.py runserver 0.0.0.0:8000

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
"""

DOCKER_COMPOSE_NODE_NEXTJS = """services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    environment:
      - NODE_ENV=development
    command: npm run dev

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
"""

DOCKER_COMPOSE_FULLSTACK = """services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "6100:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://app:app@db:5432/app
      - SECRET_KEY=dev-secret-key-change-in-production
    depends_on:
      db:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    environment:
      - NODE_ENV=development
      - NEXT_PUBLIC_API_URL=http://localhost:6100
    depends_on:
      - backend
    command: npm run dev

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
"""

DOCKER_COMPOSE_GO = """services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "6100:8080"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://app:app@db:5432/app
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
"""

# =============================================================================
# Dockerfile Templates
# =============================================================================

DOCKERFILE_PYTHON = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
"""

DOCKERFILE_PYTHON_DJANGO = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
"""

DOCKERFILE_NODE = """FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better caching
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Default command
CMD ["npm", "run", "dev"]
"""

DOCKERFILE_GO = """FROM golang:1.21-alpine

WORKDIR /app

# Install air for hot reload
RUN go install github.com/cosmtrek/air@latest

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Default command with hot reload
CMD ["air", "-c", ".air.toml"]
"""

# =============================================================================
# Other Templates
# =============================================================================

DOCKERIGNORE = """# Git
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
venv/
.venv/
*.egg-info/
.eggs/
dist/
build/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
.next/
.nuxt/
dist/
coverage/
.npm/

# Go
/bin
/pkg

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local
.env.*.local

# Docker
Dockerfile*
docker-compose*.yml
.docker/

# Misc
*.log
*.tmp
.DS_Store
Thumbs.db
"""

REQUIREMENTS_FASTAPI = """fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
httpx>=0.26.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
"""

REQUIREMENTS_DJANGO = """Django>=5.0
psycopg2-binary>=2.9.9
djangorestframework>=3.14.0
django-cors-headers>=4.3.1
python-dotenv>=1.0.0
gunicorn>=21.2.0
pytest>=7.4.0
pytest-django>=4.7.0
"""


# =============================================================================
# Scaffolding Functions
# =============================================================================


def scaffold_docker_project(
    project_dir: Path,
    project_type: Optional[str] = None,
    force: bool = False,
) -> dict[str, Path]:
    """
    Create Docker configuration for a project.

    Args:
        project_dir: Path to project directory
        project_type: Override detected type ("python-fastapi", "python-django",
                     "node-nextjs", "fullstack", "go")
        force: Overwrite existing files

    Returns:
        Dict of created files {filename: path}
    """
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    created_files: dict[str, Path] = {}

    # Detect project type if not specified
    if project_type is None:
        info = detect_project_type(project_dir)
        project_type = _determine_scaffold_type(info)

    # Select templates based on type
    templates = _get_templates_for_type(project_type)

    # Create files
    for filename, content in templates.items():
        file_path = project_dir / filename

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip if exists and not forcing
        if file_path.exists() and not force:
            continue

        file_path.write_text(content)
        created_files[filename] = file_path

    return created_files


def _determine_scaffold_type(info: ProjectTypeInfo) -> str:
    """Determine scaffold type from project info."""
    if info.is_fullstack:
        return "fullstack"

    if info.primary_type == "python":
        if info.framework == "django":
            return "python-django"
        return "python-fastapi"  # Default for Python

    if info.primary_type == "node":
        if info.framework == "nextjs":
            return "node-nextjs"
        return "node-nextjs"  # Default for Node

    if info.primary_type == "go":
        return "go"

    return "python-fastapi"  # Default fallback


def _get_templates_for_type(project_type: str) -> dict[str, str]:
    """Get template files for a project type."""
    templates: dict[str, str] = {
        ".dockerignore": DOCKERIGNORE,
    }

    if project_type == "python-fastapi":
        templates["docker-compose.yml"] = DOCKER_COMPOSE_PYTHON_FASTAPI
        templates["backend/Dockerfile"] = DOCKERFILE_PYTHON
        templates["backend/requirements.txt"] = REQUIREMENTS_FASTAPI

    elif project_type == "python-django":
        templates["docker-compose.yml"] = DOCKER_COMPOSE_PYTHON_DJANGO
        templates["backend/Dockerfile"] = DOCKERFILE_PYTHON_DJANGO
        templates["backend/requirements.txt"] = REQUIREMENTS_DJANGO

    elif project_type == "node-nextjs":
        templates["docker-compose.yml"] = DOCKER_COMPOSE_NODE_NEXTJS
        templates["frontend/Dockerfile"] = DOCKERFILE_NODE

    elif project_type == "fullstack":
        templates["docker-compose.yml"] = DOCKER_COMPOSE_FULLSTACK
        templates["backend/Dockerfile"] = DOCKERFILE_PYTHON
        templates["backend/requirements.txt"] = REQUIREMENTS_FASTAPI
        templates["frontend/Dockerfile"] = DOCKERFILE_NODE

    elif project_type == "go":
        templates["docker-compose.yml"] = DOCKER_COMPOSE_GO
        templates["backend/Dockerfile"] = DOCKERFILE_GO

    else:
        # Default to Python FastAPI
        templates["docker-compose.yml"] = DOCKER_COMPOSE_PYTHON_FASTAPI
        templates["backend/Dockerfile"] = DOCKERFILE_PYTHON
        templates["backend/requirements.txt"] = REQUIREMENTS_FASTAPI

    return templates


def ensure_docker_config(project_dir: Path) -> bool:
    """
    Ensure project has Docker configuration.

    Creates minimal Docker config if missing.

    Returns:
        True if Docker config exists or was created
    """
    project_dir = Path(project_dir)

    # Check if already has Docker config
    docker_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml"]
    for df in docker_files:
        if (project_dir / df).exists():
            return True

    # Create Docker config
    try:
        scaffold_docker_project(project_dir)
        return True
    except Exception:
        return False


def get_compose_services(project_dir: Path) -> list[str]:
    """
    Get list of services defined in docker-compose.yml.

    Returns:
        List of service names
    """
    import yaml

    compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]

    for compose_file in compose_files:
        compose_path = project_dir / compose_file
        if compose_path.exists():
            try:
                with open(compose_path) as f:
                    compose = yaml.safe_load(f)
                    return list(compose.get("services", {}).keys())
            except Exception:
                pass

    return []
