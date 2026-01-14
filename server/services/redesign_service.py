"""
Redesign Service
================

Main service for managing frontend redesign operations. Coordinates
between token extraction, framework detection, and implementation
phases with user approval gates.

This service manages the full redesign workflow:
1. Reference collection (images, URLs, Figma)
2. Design token extraction via Claude Vision API
3. Change plan generation
4. Phase-by-phase implementation with approvals
5. Verification with visual comparison
"""

import asyncio
import base64
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import RedesignSession, RedesignApproval
from server.services.screenshot_service import get_screenshot_service

logger = logging.getLogger(__name__)


class RedesignService:
    """
    Service for managing frontend redesign operations.

    Handles the full lifecycle of a redesign session from reference
    collection through implementation and verification.
    """

    def __init__(self, db: Session, project_dir: Path):
        """
        Initialize the redesign service.

        Args:
            db: SQLAlchemy database session
            project_dir: Root directory of the target project
        """
        self.db = db
        self.project_dir = project_dir
        self._anthropic_client = None

    @property
    def anthropic_client(self):
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic
                self._anthropic_client = Anthropic()
            except ImportError:
                raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic")
        return self._anthropic_client

    async def create_session(self, project_name: str) -> RedesignSession:
        """
        Create a new redesign session.

        Args:
            project_name: Name of the project being redesigned

        Returns:
            New RedesignSession instance
        """
        session = RedesignSession(
            project_name=project_name,
            status="collecting",
            current_phase="references",
            references=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Created redesign session {session.id} for {project_name}")
        return session

    async def get_session(self, session_id: int) -> Optional[RedesignSession]:
        """Get a redesign session by ID."""
        return self.db.query(RedesignSession).filter(RedesignSession.id == session_id).first()

    async def get_active_session(self, project_name: str) -> Optional[RedesignSession]:
        """Get the active (non-complete) redesign session for a project."""
        return (
            self.db.query(RedesignSession)
            .filter(
                RedesignSession.project_name == project_name,
                RedesignSession.status != "complete",
                RedesignSession.status != "failed",
            )
            .order_by(RedesignSession.created_at.desc())
            .first()
        )

    async def add_reference(
        self,
        session_id: int,
        ref_type: str,
        data: str,
        metadata: Optional[dict] = None,
    ) -> RedesignSession:
        """
        Add a reference to a redesign session.

        Args:
            session_id: ID of the redesign session
            ref_type: Type of reference ('image', 'url', 'figma')
            data: Reference data (base64 for images, URL string for others)
            metadata: Optional metadata (filename, dimensions, etc.)

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status != "collecting":
            raise ValueError(f"Cannot add references in status: {session.status}")

        # Process URL references by taking screenshot
        processed_data = data
        if ref_type == "url":
            screenshot_service = get_screenshot_service()
            try:
                processed_data = await screenshot_service.capture_url_as_base64(data)
                metadata = metadata or {}
                metadata["original_url"] = data
            except Exception as e:
                logger.error(f"Failed to capture URL {data}: {e}")
                raise ValueError(f"Failed to capture URL: {e}")

        # Add reference
        references = session.references or []
        references.append({
            "type": ref_type,
            "data": processed_data,
            "metadata": metadata or {},
            "added_at": datetime.utcnow().isoformat(),
        })

        session.references = references
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Added {ref_type} reference to session {session_id}")
        return session

    async def extract_tokens(self, session_id: int) -> RedesignSession:
        """
        Extract design tokens from session references using Claude Vision.

        Supports extraction from:
        - Image references (PNG, JPG, WebP via Vision API)
        - URL references (screenshots via Vision API)
        - Component code (via linked ComponentReferenceSession)

        Args:
            session_id: ID of the redesign session

        Returns:
            Updated session with extracted tokens
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Check for both references AND linked component session
        has_references = session.references and len(session.references) > 0
        has_components = session.component_session_id is not None

        if not has_references and not has_components:
            raise ValueError("No references or components to extract tokens from")

        session.status = "extracting"
        session.current_phase = "tokens"
        self.db.commit()

        try:
            # Extract tokens from each reference
            all_tokens = []

            # Extract from image references
            if has_references:
                for ref in session.references:
                    if ref["type"] in ("image", "url"):
                        tokens = await self._extract_tokens_from_image(ref["data"])
                        all_tokens.append(tokens)
                    elif ref["type"] == "figma":
                        # TODO: Implement Figma MCP integration
                        pass

            # Extract from linked component code
            if has_components:
                component_tokens = await self._extract_tokens_from_components(
                    session.component_session_id
                )
                if component_tokens:
                    all_tokens.append(component_tokens)

            # Merge tokens from multiple references
            merged_tokens = await self._merge_tokens(all_tokens)

            # Normalize tokens
            normalized = self._normalize_tokens(merged_tokens)

            session.extracted_tokens = normalized
            session.status = "planning"
            session.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(session)

            logger.info(f"Extracted tokens for session {session_id}")
            return session

        except Exception as e:
            session.status = "failed"
            session.error_message = str(e)
            self.db.commit()
            logger.error(f"Token extraction failed: {e}")
            raise

    async def _extract_tokens_from_image(self, image_base64: str) -> dict:
        """
        Extract design tokens from a base64 image using Claude Vision.

        Args:
            image_base64: Base64-encoded image data

        Returns:
            Dictionary of extracted tokens
        """
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

        message = self.anthropic_client.messages.create(
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
        import re
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            return json.loads(json_match.group(0))

        raise ValueError("Could not extract JSON from Vision API response")

    async def _extract_tokens_from_components(self, component_session_id: int) -> Optional[dict]:
        """
        Extract design tokens from component code in a linked ComponentReferenceSession.

        Analyzes React/Vue/Svelte component code to extract:
        - Tailwind class colors (bg-blue-500, text-gray-900)
        - CSS custom properties (--color-primary)
        - Inline style colors and spacing
        - Spacing patterns from Tailwind classes

        Args:
            component_session_id: ID of the ComponentReferenceSession

        Returns:
            Dictionary of extracted tokens, or None if no components found
        """
        from api.database import ComponentReferenceSession

        component_session = self.db.query(ComponentReferenceSession).filter(
            ComponentReferenceSession.id == component_session_id
        ).first()

        if not component_session or not component_session.components:
            logger.warning(f"No components found in session {component_session_id}")
            return None

        # Collect component code snippets (limit to first 10 to avoid token limits)
        components = component_session.components
        code_snippets = []

        for comp in components[:10]:
            if comp.get("file_type") == "component":
                content = comp.get("content", "")[:3000]  # Limit content size
                code_snippets.append(f"// {comp['filename']}\n{content}")

        if not code_snippets:
            logger.warning(f"No component code found in session {component_session_id}")
            return None

        combined_code = "\n\n---\n\n".join(code_snippets)

        prompt = """Analyze these UI component code files and extract design tokens.

Look for:
1. Tailwind classes: bg-*, text-*, border-*, p-*, m-*, gap-*, rounded-*, shadow-*
2. CSS variables: --color-*, --spacing-*, --radius-*
3. Inline styles with colors and spacing
4. CSS-in-JS theme values
5. Color definitions in constants/config files

Output as JSON:
{
  "colors": {
    "primary": {"500": "#HEXVAL"},
    "secondary": {"500": "#HEXVAL"},
    "neutral": {"50": "#...", "100": "#...", "500": "#...", "900": "#..."}
  },
  "typography": {
    "fontFamily": {"sans": ["Font Name", "fallback"]}
  },
  "spacing": {"4": "16px", "8": "32px"},
  "borders": {"radius": {"md": "8px"}},
  "shadows": {"md": "shadow value"}
}

Infer hex values from Tailwind class names if needed:
- blue-500 = #3B82F6
- gray-900 = #111827
- green-500 = #22C55E
- red-500 = #EF4444

Return ONLY valid JSON.

Component code to analyze:
""" + combined_code

        try:
            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # Try to find JSON in response
            import re
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                tokens = json.loads(json_match.group(0))
                logger.info(
                    f"Extracted tokens from {len(code_snippets)} components "
                    f"in session {component_session_id}"
                )
                return tokens

            logger.warning("Could not extract JSON from component analysis response")
            return None

        except Exception as e:
            logger.error(f"Component token extraction failed: {e}")
            return None

    async def _merge_tokens(self, token_sets: list[dict]) -> dict:
        """
        Merge multiple token sets into one.

        Later sets take priority for conflicting values.
        """
        if not token_sets:
            return {}

        if len(token_sets) == 1:
            return token_sets[0]

        result = {}
        for tokens in token_sets:
            result = self._deep_merge(result, tokens)

        return result

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries."""
        import copy
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _normalize_tokens(self, tokens: dict) -> dict:
        """
        Normalize tokens to ensure all required fields exist.

        Fills in missing values with sensible defaults.
        """
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

    async def generate_plan(self, session_id: int) -> RedesignSession:
        """
        Generate an implementation plan based on extracted tokens.

        Args:
            session_id: ID of the redesign session

        Returns:
            Updated session with change plan
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.extracted_tokens:
            raise ValueError("No tokens extracted yet")

        # Detect framework
        from lib.framework_detector import detect_framework
        framework_info = detect_framework(self.project_dir)
        session.framework_detected = framework_info.identifier

        # Generate plan based on framework
        plan = await self._generate_change_plan(
            session.extracted_tokens,
            framework_info,
        )

        session.change_plan = plan
        session.status = "approving"
        session.current_phase = "plan"
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Generated plan for session {session_id}")
        return session

    async def _generate_change_plan(
        self,
        tokens: dict,
        framework_info: Any,
    ) -> dict:
        """
        Generate a change plan for the detected framework.

        Returns a structured plan with phases and file changes.
        """
        from lib.framework_detector import get_output_format

        output_format = get_output_format(framework_info)

        phases = []

        # Phase 1: Global CSS
        if framework_info.globals_css_path:
            phases.append({
                "name": "globals",
                "description": "Update global CSS variables",
                "files": [{
                    "path": str(framework_info.globals_css_path),
                    "action": "modify",
                    "changes": self._generate_css_changes(tokens),
                }]
            })

        # Phase 2: Tailwind config (if applicable)
        if framework_info.tailwind_config_path:
            phases.append({
                "name": "config",
                "description": "Update Tailwind configuration",
                "files": [{
                    "path": str(framework_info.tailwind_config_path),
                    "action": "modify",
                    "changes": self._generate_tailwind_changes(tokens),
                }]
            })

        # Phase 3: Theme config (if applicable)
        if framework_info.theme_config_path:
            phases.append({
                "name": "theme",
                "description": "Update theme configuration",
                "files": [{
                    "path": str(framework_info.theme_config_path),
                    "action": "modify",
                    "changes": self._generate_theme_changes(tokens, framework_info.ui_library),
                }]
            })

        return {
            "output_format": output_format,
            "framework": framework_info.identifier,
            "phases": phases,
        }

    def _generate_css_changes(self, tokens: dict) -> list[dict]:
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

    def _generate_tailwind_changes(self, tokens: dict) -> list[dict]:
        """Generate Tailwind config changes from tokens."""
        return [{
            "type": "theme_extend",
            "section": "colors",
            "newValue": tokens.get("colors", {}),
        }]

    def _generate_theme_changes(self, tokens: dict, ui_library: Optional[str]) -> list[dict]:
        """Generate UI library theme changes from tokens."""
        if ui_library == "shadcn":
            return [{
                "type": "shadcn_theme",
                "newValue": tokens,
            }]
        return []

    async def approve_phase(
        self,
        session_id: int,
        phase: str,
        modifications: Optional[dict] = None,
        comment: Optional[str] = None,
    ) -> RedesignSession:
        """
        Approve a phase of the redesign plan.

        Args:
            session_id: ID of the redesign session
            phase: Phase name to approve
            modifications: Optional modifications to the plan
            comment: Optional user comment

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Create approval record
        approval = RedesignApproval(
            session_id=session_id,
            phase=phase,
            approved=True,
            modifications=modifications,
            comment=comment,
            approved_at=datetime.utcnow(),
        )
        self.db.add(approval)

        # Update session
        session.current_phase = phase
        session.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Approved phase '{phase}' for session {session_id}")
        return session

    async def get_phase_approval(
        self,
        session_id: int,
        phase: str,
    ) -> Optional[RedesignApproval]:
        """Check if a phase has been approved."""
        return (
            self.db.query(RedesignApproval)
            .filter(
                RedesignApproval.session_id == session_id,
                RedesignApproval.phase == phase,
                RedesignApproval.approved == True,
            )
            .first()
        )

    async def complete_session(self, session_id: int) -> RedesignSession:
        """Mark a redesign session as complete."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = "complete"
        session.current_phase = "verification"
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Completed redesign session {session_id}")
        return session

    async def fail_session(self, session_id: int, error: str) -> RedesignSession:
        """Mark a redesign session as failed."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = "failed"
        session.error_message = error
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.error(f"Failed redesign session {session_id}: {error}")
        return session
