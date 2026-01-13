"""
FastAPI Main Application
========================

Main entry point for the Autonomous Coding UI server.
Provides REST API, WebSocket, and static file serving.
"""

import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .routers import (
    agent_router,
    assistant_chat_router,
    auth_router,
    features_router,
    filesystem_router,
    projects_router,
    spec_creation_router,
    spec_import_router,
)
from .routers.auth import get_current_user
from .schemas import SetupStatus
from .services.assistant_chat_session import cleanup_all_sessions as cleanup_assistant_sessions
from .services.process_manager import cleanup_all_managers
from .websocket import project_websocket
from .lib.path_security import config as path_config

# Paths
ROOT_DIR = Path(__file__).parent.parent
UI_DIST_DIR = ROOT_DIR / "ui" / "dist"

# Rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)

# Check if authentication is required
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"

# CORS origins from environment (comma-separated list or "*" for all)
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "")
if CORS_ORIGINS_ENV == "*":
    CORS_ORIGINS = ["*"]
elif CORS_ORIGINS_ENV:
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_ENV.split(",")]
else:
    # Default origins for localhost
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8888",
        "http://127.0.0.1:8888",
    ]

# Public routes that don't require authentication
PUBLIC_ROUTES = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/health",
    "/api/setup/status",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    yield
    # Shutdown - cleanup all running agents and assistant sessions
    await cleanup_all_managers()
    await cleanup_assistant_sessions()


# Create FastAPI app
app = FastAPI(
    title="Autonomous Coding UI",
    description="Web UI for the Autonomous Coding Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiter to app state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - configurable via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Security Middleware
# ============================================================================

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Security middleware: localhost check and authentication."""
    # 1. Localhost check (if enabled)
    if path_config.require_localhost:
        client_host = request.client.host if request.client else None
        if client_host not in ("127.0.0.1", "::1", "localhost", None):
            return JSONResponse(
                status_code=403,
                content={"detail": "Localhost access only"}
            )

    # 2. Authentication check (if enabled)
    if AUTH_ENABLED:
        path = request.url.path

        # Skip auth for public routes and static files
        is_public = (
            path in PUBLIC_ROUTES
            or path.startswith("/assets/")
            or path == "/"
            or not path.startswith("/api/")
        )

        if not is_public:
            user = await get_current_user(request)
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Not authenticated"}
                )

    return await call_next(request)


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(features_router)
app.include_router(agent_router)
app.include_router(spec_creation_router)
app.include_router(spec_import_router)
app.include_router(filesystem_router)
app.include_router(assistant_chat_router)


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/projects/{project_name}")
async def websocket_endpoint(websocket: WebSocket, project_name: str):
    """WebSocket endpoint for real-time project updates."""
    await project_websocket(websocket, project_name)


# ============================================================================
# Setup & Health Endpoints
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/setup/status", response_model=SetupStatus)
async def setup_status():
    """Check system setup status."""
    # Check for Claude CLI
    claude_cli = shutil.which("claude") is not None

    # Check for credentials file
    credentials_path = Path.home() / ".claude" / ".credentials.json"
    credentials = credentials_path.exists()

    # Check for Node.js and npm
    node = shutil.which("node") is not None
    npm = shutil.which("npm") is not None

    return SetupStatus(
        claude_cli=claude_cli,
        credentials=credentials,
        node=node,
        npm=npm,
    )


# ============================================================================
# Static File Serving (Production)
# ============================================================================

# Serve React build files if they exist
if UI_DIST_DIR.exists():
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=UI_DIST_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_index():
        """Serve the React app index.html."""
        return FileResponse(UI_DIST_DIR / "index.html")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """
        Serve static files or fall back to index.html for SPA routing.
        """
        # Check if the path is an API route (shouldn't hit this due to router ordering)
        if path.startswith("api/") or path.startswith("ws/"):
            raise HTTPException(status_code=404)

        # Try to serve the file directly
        file_path = UI_DIST_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Fall back to index.html for SPA routing
        return FileResponse(UI_DIST_DIR / "index.html")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",  # Localhost only for security
        port=8888,
        reload=True,
    )
