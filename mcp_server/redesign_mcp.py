#!/usr/bin/env python3
"""
MCP Server for Redesign Operations
===================================

Provides tools for the autonomous agent to perform full frontend redesign
based on reference images, URLs, and Figma files.

Tools:
- redesign_get_status: Get current redesign session status
- redesign_start_session: Initialize a new redesign session
- redesign_add_image_reference: Add image reference (base64)
- redesign_add_url_reference: Add URL reference (stored only)
- redesign_extract_tokens: Deprecated (planner handles extraction)
- redesign_save_tokens: Save design tokens from planner
- redesign_save_plan: Save plan from planner
- redesign_generate_plan: Deprecated (planner handles planning)
- redesign_check_approval: Check if a phase is approved
- redesign_apply_changes: Apply token changes to files
- redesign_take_screenshot: Capture screenshot for verification
- redesign_complete_session: Mark session as complete
"""

import asyncio
import base64
import json
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import Feature, RedesignSession, RedesignApproval, create_database

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()

# Global database session maker (initialized on startup)
_session_maker = None
_engine = None
_anthropic_client = None
_screenshot_service = None


def get_anthropic_client():
    """Lazy-load Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        try:
            from anthropic import Anthropic
            _anthropic_client = Anthropic()
        except ImportError:
            raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic")
    return _anthropic_client


async def get_screenshot_service():
    """Get the screenshot service (lazy-initialized)."""
    global _screenshot_service
    if _screenshot_service is None:
        from apps.server.services.screenshot_service import ScreenshotService
        _screenshot_service = ScreenshotService()
    return _screenshot_service


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize database on startup, cleanup on shutdown."""
    global _session_maker, _engine, _screenshot_service

    # Initialize database
    _engine, _session_maker = create_database(PROJECT_DIR)

    yield

    # Cleanup
    if _screenshot_service:
        await _screenshot_service.close()
        _screenshot_service = None

    if _engine:
        _engine.dispose()


# Initialize the MCP server
mcp = FastMCP("redesign", lifespan=server_lifespan)


def get_session():
    """Get a new database session."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized")
    return _session_maker()


def get_active_session_sync(project_name: str) -> Optional[RedesignSession]:
    """Get the active redesign session for a project (synchronous)."""
    session = get_session()
    try:
        return (
            session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )
    finally:
        session.close()


@mcp.tool()
def redesign_get_status() -> str:
    """Get the status of the active redesign session.

    Returns the current session with its status, references count,
    extracted tokens preview, and change plan overview.

    Use this at the start of a redesign task to understand the current state.

    Returns:
        JSON with session details or message if no active session.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "has_session": False,
                "message": "No active redesign session. Use redesign_start_session to begin."
            })

        # Build response
        response = {
            "has_session": True,
            "session_id": session.id,
            "status": session.status,
            "current_phase": session.current_phase,
            "framework_detected": session.framework_detected,
            "references_count": len(session.references or []),
            "has_tokens": session.extracted_tokens is not None,
            "has_plan": session.change_plan is not None,
        }

        # Add tokens preview if available
        if session.extracted_tokens:
            tokens = session.extracted_tokens
            response["tokens_preview"] = {
                "color_categories": list(tokens.get("colors", {}).keys()),
                "has_typography": "typography" in tokens,
                "has_spacing": "spacing" in tokens,
            }

        # Add plan overview if available
        if session.change_plan:
            plan = session.change_plan
            response["plan_overview"] = {
                "output_format": plan.get("output_format"),
                "phases_count": len(plan.get("phases", [])),
                "phases": [p.get("name") for p in plan.get("phases", [])],
            }

        if session.error_message:
            response["error_message"] = session.error_message

        return json.dumps(response, indent=2)
    finally:
        db_session.close()


@mcp.tool()
def redesign_get_references() -> str:
    """Get the raw references for the active redesign session.

    Returns the stored references (image base64 or URL strings) plus metadata.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "has_session": False,
                "references": [],
                "message": "No active redesign session."
            })

        return json.dumps({
            "has_session": True,
            "session_id": session.id,
            "references": session.references or [],
        }, indent=2)
    finally:
        db_session.close()


@mcp.tool()
def redesign_start_session() -> str:
    """Start a new redesign session for the current project.

    Creates a new session in 'collecting' status, ready to receive
    reference images or URLs. If an active session exists, returns it.

    Returns:
        JSON with the session details.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        # Check for existing active session
        existing = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .first()
        )

        if existing:
            return json.dumps({
                "action": "resumed",
                "session_id": existing.id,
                "status": existing.status,
                "message": f"Resumed existing session {existing.id} in status '{existing.status}'"
            })

        # Create new session
        session = RedesignSession(
            project_name=project_name,
            status="collecting",
            current_phase="references",
            references=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        return json.dumps({
            "action": "created",
            "session_id": session.id,
            "status": session.status,
            "message": "New redesign session created. Add references using redesign_add_image_reference or redesign_add_url_reference."
        }, indent=2)
    finally:
        db_session.close()


@mcp.tool()
def redesign_add_image_reference(
    image_base64: Annotated[str, Field(description="Base64-encoded image data (PNG, JPG, or WebP)")],
    filename: Annotated[str, Field(description="Original filename")] = "reference.png",
) -> str:
    """Add an image reference to the active redesign session.

    Use this to add design reference images (screenshots, mockups, etc.)
    that will be analyzed for design token extraction.

    Args:
        image_base64: Base64-encoded image data
        filename: Original filename for reference

    Returns:
        JSON with updated reference count.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status == "collecting",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session in 'collecting' status. Start a new session first."
            })

        # Add reference
        references = session.references or []
        references.append({
            "type": "image",
            "data": image_base64,
            "metadata": {
                "filename": filename,
                "added_at": datetime.utcnow().isoformat(),
            },
        })

        session.references = references
        session.updated_at = datetime.utcnow()
        db_session.commit()

        return json.dumps({
            "success": True,
            "references_count": len(references),
            "message": f"Added image reference '{filename}'. Total references: {len(references)}"
        })
    finally:
        db_session.close()


@mcp.tool()
def redesign_add_url_reference(
    url: Annotated[str, Field(description="URL to capture screenshot from")],
) -> str:
    """Add a URL reference to the active redesign session.

    Stores the URL for agent-side inspection (no server-side screenshot).
    Use this to reference existing websites or live designs.

    Args:
        url: The URL to capture

    Returns:
        JSON with updated reference count.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status == "collecting",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session in 'collecting' status. Start a new session first."
            })

        # Add reference
        references = session.references or []
        references.append({
            "type": "url",
            "data": url,
            "metadata": {
                "original_url": url,
                "added_at": datetime.utcnow().isoformat(),
            },
        })

        session.references = references
        session.updated_at = datetime.utcnow()
        db_session.commit()

        return json.dumps({
            "success": True,
            "references_count": len(references),
            "message": f"Added URL reference '{url}'. Total references: {len(references)}"
        })
    finally:
        db_session.close()


@mcp.tool()
def redesign_extract_tokens() -> str:
    """Extract design tokens from all references in the active session.

    Uses Claude Vision API to analyze reference images and extract:
    - Colors (primary, secondary, neutral, semantic)
    - Typography (font families, sizes, weights)
    - Spacing (margins, padding scale)
    - Borders (radius, width)
    - Shadows

    Must have at least one reference added before calling this.

    Returns:
        JSON with extracted tokens or error.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active redesign session."
            })

        if session.extracted_tokens:
            return json.dumps({
                "success": True,
                "tokens": session.extracted_tokens,
                "message": "Tokens already saved by redesign planner."
            }, indent=2)

        return json.dumps({
            "error": "This tool is deprecated. Use the redesign planner agent and redesign_save_tokens."
        })
    finally:
        db_session.close()


@mcp.tool()
def redesign_save_tokens(
    tokens: Annotated[dict, Field(description="Design tokens JSON object")],
) -> str:
    """Save design tokens produced by the redesign planner agent."""
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({"error": "No active redesign session."})

        session.extracted_tokens = tokens
        session.status = "planning"
        session.current_phase = "tokens"
        session.updated_at = datetime.utcnow()
        db_session.commit()

        return json.dumps({
            "success": True,
            "message": "Design tokens saved.",
        })
    finally:
        db_session.close()


@mcp.tool()
def redesign_save_plan(
    plan: Annotated[dict, Field(description="Redesign plan JSON object")],
) -> str:
    """Save a redesign plan produced by the planner agent."""
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({"error": "No active redesign session."})

        session.change_plan = plan
        session.status = "approving"
        session.current_phase = "plan"
        session.updated_at = datetime.utcnow()
        db_session.commit()

        _ensure_redesign_feature(db_session, session, plan)

        return json.dumps({
            "success": True,
            "message": "Redesign plan saved.",
        })
    finally:
        db_session.close()


def _ensure_redesign_feature(db_session, session: RedesignSession, plan: dict) -> None:
    """Create a single redesign Feature linked to this session if missing."""
    existing = (
        db_session.query(Feature)
        .filter(
            Feature.item_type == "redesign",
            Feature.redesign_session_id == session.id,
        )
        .first()
    )

    phase_names = []
    for phase in plan.get("phases", []):
        if isinstance(phase, dict) and phase.get("name"):
            phase_names.append(phase["name"])

    phases_summary = ", ".join(phase_names) if phase_names else "approved phases"
    steps = [
        "Mark the redesign task in progress.",
        "Fetch design tokens and the change plan.",
        f"Apply the plan for: {phases_summary}.",
        "Complete the redesign session after applying changes.",
    ]

    if existing:
        existing.name = "Apply redesign plan"
        existing.description = (
            f"Apply redesign plan for session {session.id} "
            f"({session.project_name})."
        )
        existing.category = "redesign"
        existing.steps = steps
        existing.arch_layer = 6
        db_session.commit()
        return

    feature = Feature(
        priority=0,
        category="redesign",
        name="Apply redesign plan",
        description=(
            f"Apply redesign plan for session {session.id} "
            f"({session.project_name})."
        ),
        steps=steps,
        passes=False,
        in_progress=False,
        item_type="redesign",
        arch_layer=6,
        redesign_session_id=session.id,
        source_spec="redesign",
    )
    db_session.add(feature)
    db_session.commit()


def _extract_tokens_from_image(client, image_base64: str) -> dict:
    """Extract design tokens from an image using Claude Vision."""
    prompt = """Analyze this UI design image and extract design tokens.

Output as JSON with this structure:
{
  "colors": {
    "primary": {"500": "#HEXVAL"},
    "secondary": {"500": "#HEXVAL"},
    "neutral": {"50": "#...", "100": "#...", "500": "#...", "900": "#..."},
    "semantic": {
      "success": {"DEFAULT": "#HEXVAL"},
      "error": {"DEFAULT": "#HEXVAL"},
      "warning": {"DEFAULT": "#HEXVAL"},
      "info": {"DEFAULT": "#HEXVAL"}
    }
  },
  "typography": {
    "fontFamily": {"sans": ["Font Name", "fallback"]},
    "fontSize": {"base": {"value": "16px"}},
    "fontWeight": {"normal": 400, "bold": 700}
  },
  "spacing": {"4": "16px", "8": "32px"},
  "borders": {"radius": {"md": "8px"}},
  "shadows": {"md": "0 4px 6px rgba(0,0,0,0.1)"}
}

Extract what you can see. Use hex colors. Return ONLY valid JSON."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    # Parse JSON from response
    response_text = message.content[0].text

    # Try to find JSON in response
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if json_match:
        return json.loads(json_match.group(0))

    raise ValueError("Could not extract JSON from Vision API response")


def _merge_tokens(token_sets: list[dict]) -> dict:
    """Merge multiple token sets into one."""
    if not token_sets:
        return {}

    if len(token_sets) == 1:
        return token_sets[0]

    result = {}
    for tokens in token_sets:
        result = _deep_merge(result, tokens)

    return result


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    import copy
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


def _normalize_tokens(tokens: dict) -> dict:
    """Normalize tokens to ensure all required fields exist."""
    # Add schema version
    tokens["$schema"] = "design-tokens-v1"

    # Ensure colors have full scales
    if "colors" in tokens:
        if "neutral" not in tokens["colors"]:
            tokens["colors"]["neutral"] = {
                "50": "#FAFAFA",
                "100": "#F5F5F5",
                "500": "#737373",
                "900": "#171717",
            }

    # Ensure typography defaults
    if "typography" not in tokens:
        tokens["typography"] = {}

    if "fontFamily" not in tokens["typography"]:
        tokens["typography"]["fontFamily"] = {
            "sans": ["Inter", "system-ui", "sans-serif"]
        }

    return tokens


@mcp.tool()
def redesign_generate_plan() -> str:
    """Generate an implementation plan based on extracted tokens.

    Detects the project framework (React/Vue, Tailwind, Shadcn, etc.)
    and generates a plan for applying design tokens.

    Must have tokens extracted before calling this.

    Returns:
        JSON with the generated plan.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status == "planning",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session in 'planning' status. Extract tokens first."
            })

        if not session.extracted_tokens:
            return json.dumps({
                "error": "No tokens extracted. Run redesign_extract_tokens first."
            })

        try:
            # Detect framework
            from lib.framework_detector import detect_framework, get_output_format
            framework_info = detect_framework(PROJECT_DIR)
            session.framework_detected = framework_info.identifier

            # Generate plan
            output_format = get_output_format(framework_info)
            tokens = session.extracted_tokens

            phases = []

            # Phase 1: Global CSS
            if framework_info.globals_css_path:
                phases.append({
                    "name": "globals",
                    "description": "Update global CSS variables",
                    "files": [{
                        "path": str(framework_info.globals_css_path),
                        "action": "modify",
                        "changes": _generate_css_changes(tokens),
                    }]
                })

            # Phase 2: Tailwind config
            if framework_info.tailwind_config_path:
                phases.append({
                    "name": "config",
                    "description": "Update Tailwind configuration",
                    "files": [{
                        "path": str(framework_info.tailwind_config_path),
                        "action": "modify",
                        "changes": [{
                            "type": "theme_extend",
                            "section": "colors",
                            "newValue": tokens.get("colors", {}),
                        }],
                    }]
                })

            # Phase 3: Theme config
            if framework_info.theme_config_path:
                phases.append({
                    "name": "theme",
                    "description": "Update theme configuration",
                    "files": [{
                        "path": str(framework_info.theme_config_path),
                        "action": "modify",
                        "changes": [{
                            "type": "theme_update",
                            "ui_library": framework_info.ui_library,
                            "newValue": tokens,
                        }],
                    }]
                })

            plan = {
                "output_format": output_format,
                "framework": framework_info.identifier,
                "phases": phases,
            }

            session.change_plan = plan
            session.status = "approving"
            session.current_phase = "plan"
            session.updated_at = datetime.utcnow()
            db_session.commit()

            return json.dumps({
                "success": True,
                "framework": framework_info.identifier,
                "output_format": output_format,
                "plan": plan,
                "message": "Implementation plan generated. Waiting for user approval."
            }, indent=2)

        except Exception as e:
            session.status = "failed"
            session.error_message = str(e)
            db_session.commit()
            return json.dumps({
                "error": f"Plan generation failed: {str(e)}"
            })

    finally:
        db_session.close()


def _generate_css_changes(tokens: dict) -> list[dict]:
    """Generate CSS variable changes from tokens."""
    changes = []

    if "colors" in tokens:
        for category, scale in tokens["colors"].items():
            if isinstance(scale, dict):
                for shade, value in scale.items():
                    if isinstance(value, str):
                        changes.append({
                            "type": "css_variable",
                            "name": f"--color-{category}-{shade}",
                            "newValue": value,
                        })
                    elif isinstance(value, dict) and "DEFAULT" in value:
                        changes.append({
                            "type": "css_variable",
                            "name": f"--color-{category}",
                            "newValue": value["DEFAULT"],
                        })

    return changes


@mcp.tool()
def redesign_check_approval(
    phase: Annotated[str, Field(description="Phase name to check (e.g., 'globals', 'config', 'theme')")],
) -> str:
    """Check if a specific phase has been approved by the user.

    The agent should wait for user approval before applying changes
    to each phase. This tool checks the approval status.

    Args:
        phase: The phase name to check

    Returns:
        JSON with approval status and any modifications.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status.in_(["approving", "implementing"]),
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session awaiting approval."
            })

        # Check for approval record
        approval = (
            db_session.query(RedesignApproval)
            .filter(
                RedesignApproval.session_id == session.id,
                RedesignApproval.phase == phase,
                RedesignApproval.approved == True,
            )
            .first()
        )

        if approval:
            return json.dumps({
                "approved": True,
                "phase": phase,
                "modifications": approval.modifications,
                "comment": approval.comment,
                "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
                "message": f"Phase '{phase}' is approved. Proceed with implementation."
            })

        return json.dumps({
            "approved": False,
            "phase": phase,
            "message": f"Phase '{phase}' not yet approved. Wait for user approval via the UI."
        })

    finally:
        db_session.close()


@mcp.tool()
def redesign_apply_changes(
    phase: Annotated[str, Field(description="Phase to apply (e.g., 'globals', 'config', 'theme')")],
) -> str:
    """Apply the planned changes for a specific phase.

    This tool reads the plan for the given phase and returns the
    specific file changes to make. The agent should then use the
    Edit tool to apply these changes.

    Args:
        phase: The phase to apply

    Returns:
        JSON with file changes to apply.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status.in_(["approving", "implementing"]),
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session."
            })

        if not session.change_plan:
            return json.dumps({
                "error": "No change plan generated."
            })

        if "phases" not in session.change_plan:
            return json.dumps({
                "error": "Plan is page-based. Use feature tasks instead of redesign_apply_changes."
            })

        # Find the phase in the plan
        phases = session.change_plan.get("phases", [])
        phase_data = None
        for p in phases:
            if p.get("name") == phase:
                phase_data = p
                break

        if not phase_data:
            return json.dumps({
                "error": f"Phase '{phase}' not found in plan. Available phases: {[p.get('name') for p in phases]}"
            })

        # Update status
        session.status = "implementing"
        session.current_phase = phase
        session.updated_at = datetime.utcnow()
        db_session.commit()

        return json.dumps({
            "phase": phase,
            "description": phase_data.get("description"),
            "files": phase_data.get("files", []),
            "tokens": session.extracted_tokens,
            "message": f"Apply the changes for phase '{phase}' using the Edit tool."
        }, indent=2)

    finally:
        db_session.close()


@mcp.tool()
def redesign_take_screenshot(
    url: Annotated[str, Field(description="URL to capture screenshot from")] = "http://localhost:5173",
) -> str:
    """Capture a screenshot for visual verification.

    Use this after applying changes to capture the current state
    of the application for before/after comparison.

    Args:
        url: The URL to capture (default: localhost:5173)

    Returns:
        JSON with base64 screenshot or error.
    """
    try:
        screenshot_svc = asyncio.get_event_loop().run_until_complete(
            get_screenshot_service()
        )
        image_base64 = asyncio.get_event_loop().run_until_complete(
            screenshot_svc.capture_url_as_base64(url)
        )

        return json.dumps({
            "success": True,
            "url": url,
            "screenshot_base64": image_base64[:100] + "...",  # Truncate for display
            "full_data_length": len(image_base64),
            "message": "Screenshot captured successfully."
        })

    except Exception as e:
        return json.dumps({
            "error": f"Failed to capture screenshot: {str(e)}"
        })


@mcp.tool()
def redesign_complete_session() -> str:
    """Mark the redesign session as complete.

    Call this after all phases have been implemented and verified.

    Returns:
        JSON with completion status.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session to complete."
            })

        session.status = "complete"
        session.current_phase = "verification"
        session.updated_at = datetime.utcnow()
        db_session.commit()

        return json.dumps({
            "success": True,
            "session_id": session.id,
            "message": "Redesign session completed successfully!"
        })

    finally:
        db_session.close()


@mcp.tool()
def redesign_get_tokens() -> str:
    """Get the extracted design tokens from the active session.

    Returns the full token structure for use in implementation.

    Returns:
        JSON with the design tokens.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session."
            })

        if not session.extracted_tokens:
            return json.dumps({
                "error": "No tokens extracted yet."
            })

        return json.dumps({
            "tokens": session.extracted_tokens,
            "framework": session.framework_detected,
        }, indent=2)

    finally:
        db_session.close()


@mcp.tool()
def redesign_get_plan() -> str:
    """Get the generated change plan from the active session.

    Returns the full plan structure with phases and file changes.

    Returns:
        JSON with the change plan.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session."
            })

        if not session.change_plan:
            return json.dumps({
                "error": "No plan generated yet."
            })

        return json.dumps({
            "plan": session.change_plan,
            "framework": session.framework_detected,
            "status": session.status,
        }, indent=2)

    finally:
        db_session.close()


if __name__ == "__main__":
    mcp.run()
