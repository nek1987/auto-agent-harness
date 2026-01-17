"""
Feature Analyze Router
======================

WebSocket and REST endpoints for AI-powered feature analysis.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..services.feature_analyzer import (
    FeatureAnalyzerSession,
    create_analyzer_session,
    get_analyzer_session,
    remove_analyzer_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feature-analyze", tags=["feature-analyze"])


def _get_project_path(project_name: str) -> Optional[Path]:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def validate_project_name(name: str) -> bool:
    """Validate project name to prevent path traversal."""
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,50}$', name))


# ============================================================================
# Request/Response Schemas
# ============================================================================

class FeatureAnalyzeRequest(BaseModel):
    """Request to analyze a feature."""
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    steps: list[str] = Field(default_factory=list)


class AnalyzerSessionStatus(BaseModel):
    """Status of an analyzer session."""
    project_name: str
    is_active: bool


# ============================================================================
# REST Endpoints
# ============================================================================

@router.get("/sessions/{project_name}", response_model=AnalyzerSessionStatus)
async def get_session_status(project_name: str):
    """Get status of an analyzer session."""
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    session = get_analyzer_session(project_name)

    return AnalyzerSessionStatus(
        project_name=project_name,
        is_active=session is not None,
    )


@router.delete("/sessions/{project_name}")
async def cancel_session(project_name: str):
    """Cancel and remove an analyzer session."""
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    session = get_analyzer_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active session for this project")

    await remove_analyzer_session(project_name)
    return {"success": True, "message": "Session cancelled"}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{project_name}")
async def feature_analyze_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for AI-powered feature analysis.

    Message protocol:

    Client -> Server:
    - {"type": "analyze", "feature": {...}} - Start analysis with feature data
    - {"type": "ping"} - Keep-alive ping

    Server -> Client:
    - {"type": "status", "content": "..."} - Status update
    - {"type": "text", "content": "..."} - Text chunk from Claude
    - {"type": "suggestion", "suggestion": {...}} - Single suggestion
    - {"type": "complexity", "complexity": {...}} - Complexity assessment
    - {"type": "analysis_complete"} - Analysis finished
    - {"type": "error", "content": "..."} - Error message
    - {"type": "pong"} - Keep-alive pong
    """
    if not validate_project_name(project_name):
        await websocket.close(code=4000, reason="Invalid project name")
        return

    # Look up project directory from registry
    project_dir = _get_project_path(project_name)
    if not project_dir:
        await websocket.close(code=4004, reason="Project not found in registry")
        return

    if not project_dir.exists():
        await websocket.close(code=4004, reason="Project directory not found")
        return

    await websocket.accept()

    session: Optional[FeatureAnalyzerSession] = None

    try:
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                elif msg_type == "analyze":
                    # Create session and start analysis
                    feature_data = message.get("feature", {})

                    # Validate feature data
                    name = feature_data.get("name", "").strip()
                    category = feature_data.get("category", "").strip()
                    description = feature_data.get("description", "").strip()
                    steps = feature_data.get("steps", [])

                    if not name or not description:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Feature name and description are required"
                        })
                        continue

                    # Create analyzer session
                    session = await create_analyzer_session(project_name, project_dir)

                    # Stream analysis results
                    async for chunk in session.analyze_stream(
                        name=name,
                        category=category or "uncategorized",
                        description=description,
                        steps=steps if steps else [],
                    ):
                        await websocket.send_json(chunk)

                else:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Unknown message type: {msg_type}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "content": "Invalid JSON"
                })

    except WebSocketDisconnect:
        logger.info(f"Feature analyze WebSocket disconnected for {project_name}")

    except Exception as e:
        logger.exception(f"Feature analyze WebSocket error for {project_name}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"Server error: {str(e)}"
            })
        except Exception:
            pass

    finally:
        # Clean up session on disconnect
        if session:
            try:
                await session.close()
            except Exception:
                pass
