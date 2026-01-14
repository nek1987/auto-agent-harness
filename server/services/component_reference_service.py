"""
Component Reference Service
============================

Service for managing component reference operations. Handles ZIP file parsing,
component analysis orchestration, and plan generation for creating new
components based on external references (v0.dev, shadcn/ui, etc.).

This service manages the full workflow:
1. ZIP upload and parsing
2. Component code extraction
3. Analysis coordination
4. Generation plan creation
5. Feature linking
"""

import io
import json
import logging
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import ComponentReferenceSession, Feature

logger = logging.getLogger(__name__)


# Supported file extensions for component extraction
COMPONENT_EXTENSIONS = {
    ".tsx": "typescript-react",
    ".jsx": "javascript-react",
    ".vue": "vue",
    ".svelte": "svelte",
    ".ts": "typescript",
    ".js": "javascript",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
}

# Files to skip when parsing ZIP
SKIP_PATTERNS = [
    "__MACOSX",
    ".DS_Store",
    "node_modules",
    ".git",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    ".next",
    "dist/",
    "build/",
    ".cache",
]


class ComponentReferenceService:
    """
    Service for managing component reference operations.

    Handles ZIP parsing, analysis, and plan generation for creating
    components based on external references.
    """

    def __init__(self, db: Session, project_dir: Path):
        """
        Initialize the component reference service.

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

    async def create_session(
        self,
        project_name: str,
        source_type: str = "custom",
        source_url: Optional[str] = None,
    ) -> ComponentReferenceSession:
        """
        Create a new component reference session.

        Args:
            project_name: Name of the project
            source_type: Type of source ('v0', 'shadcn', 'custom')
            source_url: Original URL if available

        Returns:
            New ComponentReferenceSession instance
        """
        session = ComponentReferenceSession(
            project_name=project_name,
            status="uploading",
            source_type=source_type,
            source_url=source_url,
            components=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Created component reference session {session.id} for {project_name}")
        return session

    async def get_session(self, session_id: int) -> Optional[ComponentReferenceSession]:
        """Get a component reference session by ID."""
        return self.db.query(ComponentReferenceSession).filter(
            ComponentReferenceSession.id == session_id
        ).first()

    async def get_active_session(self, project_name: str) -> Optional[ComponentReferenceSession]:
        """Get the active (non-complete) component reference session for a project."""
        return (
            self.db.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "complete",
                ComponentReferenceSession.status != "failed",
            )
            .order_by(ComponentReferenceSession.created_at.desc())
            .first()
        )

    async def parse_zip_file(
        self,
        session_id: int,
        file_content: bytes,
        filename: str = "components.zip",
    ) -> ComponentReferenceSession:
        """
        Parse a ZIP file and extract component files.

        Args:
            session_id: ID of the component reference session
            file_content: ZIP file content as bytes
            filename: Original filename for logging

        Returns:
            Updated session with extracted components
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status != "uploading":
            raise ValueError(f"Cannot add components in status: {session.status}")

        try:
            components = self._extract_components_from_zip(file_content)

            # Update session with components
            existing_components = session.components or []
            existing_components.extend(components)
            session.components = existing_components
            session.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(session)

            logger.info(
                f"Extracted {len(components)} components from {filename} "
                f"for session {session_id}"
            )
            return session

        except Exception as e:
            session.status = "failed"
            session.error_message = f"ZIP parsing failed: {str(e)}"
            self.db.commit()
            logger.error(f"ZIP parsing failed for session {session_id}: {e}")
            raise

    def _extract_components_from_zip(self, file_content: bytes) -> list[dict]:
        """
        Extract component files from ZIP content.

        Args:
            file_content: ZIP file bytes

        Returns:
            List of component dictionaries
        """
        components = []

        with zipfile.ZipFile(io.BytesIO(file_content), "r") as zf:
            for zip_info in zf.infolist():
                # Skip directories
                if zip_info.is_dir():
                    continue

                filepath = zip_info.filename

                # Skip unwanted files
                if self._should_skip_file(filepath):
                    continue

                # Check if file has supported extension
                ext = Path(filepath).suffix.lower()
                if ext not in COMPONENT_EXTENSIONS:
                    continue

                # Read file content
                try:
                    content = zf.read(filepath).decode("utf-8")
                except UnicodeDecodeError:
                    logger.warning(f"Could not decode {filepath} as UTF-8, skipping")
                    continue

                # Skip empty files
                if not content.strip():
                    continue

                # Detect framework and file type
                framework = self._detect_framework(filepath, content)
                file_type = self._detect_file_type(filepath, content)

                components.append({
                    "filename": Path(filepath).name,
                    "filepath": filepath,
                    "content": content,
                    "framework": framework,
                    "file_type": file_type,
                    "extension": ext,
                    "size": len(content),
                    "added_at": datetime.utcnow().isoformat(),
                })

        return components

    def _should_skip_file(self, filepath: str) -> bool:
        """Check if a file should be skipped during extraction."""
        for pattern in SKIP_PATTERNS:
            if pattern in filepath:
                return True
        return False

    def _detect_framework(self, filename: str, content: str) -> str:
        """Detect the framework used by a component."""
        filename_lower = filename.lower()
        ext = Path(filename).suffix.lower()

        # Vue files
        if ext == ".vue":
            return "vue"

        # Svelte files
        if ext == ".svelte":
            return "svelte"

        # React detection from content
        react_patterns = [
            "import React",
            "from 'react'",
            'from "react"',
            "import { useState",
            "import { useEffect",
            "import { useRef",
        ]
        is_react = any(p in content for p in react_patterns)

        if is_react:
            # Check for Tailwind
            if "className=" in content and ("tailwind" in content.lower() or
                re.search(r'className=["\'][^"\']*(?:flex|grid|p-|m-|bg-|text-)', content)):
                return "react-tailwind"
            return "react"

        # Angular detection
        if "@Component" in content or "import { Component }" in content:
            return "angular"

        # Default based on extension
        if ext in (".tsx", ".jsx"):
            return "react"
        if ext == ".ts":
            return "typescript"
        if ext == ".js":
            return "javascript"

        return "unknown"

    def _detect_file_type(self, filename: str, content: str) -> str:
        """Detect the type of file (component, hook, utility, etc.)."""
        filename_lower = filename.lower()
        base_name = Path(filename).stem.lower()

        # Check for hooks
        if base_name.startswith("use") or "hook" in filename_lower:
            return "hook"

        # Check for utilities
        if any(x in filename_lower for x in ["util", "helper", "lib", "tools"]):
            return "utility"

        # Check for types/interfaces
        if any(x in filename_lower for x in ["types", "interfaces", "models"]):
            return "types"

        # Check for styles
        ext = Path(filename).suffix.lower()
        if ext in (".css", ".scss", ".sass"):
            return "styles"

        # Check for config files
        if "config" in filename_lower or filename_lower.endswith(".config.ts"):
            return "config"

        # Default to component for React/Vue files
        if ext in (".tsx", ".jsx", ".vue", ".svelte"):
            return "component"

        return "other"

    async def add_components(
        self,
        session_id: int,
        components: list[dict],
    ) -> ComponentReferenceSession:
        """
        Add components directly (not from ZIP).

        Args:
            session_id: ID of the session
            components: List of component dicts with filename and content

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status != "uploading":
            raise ValueError(f"Cannot add components in status: {session.status}")

        existing_components = session.components or []

        for comp in components:
            if "filename" not in comp or "content" not in comp:
                continue

            framework = comp.get("framework", self._detect_framework(comp["filename"], comp["content"]))
            file_type = comp.get("file_type", self._detect_file_type(comp["filename"], comp["content"]))

            existing_components.append({
                "filename": comp["filename"],
                "filepath": comp.get("filepath", comp["filename"]),
                "content": comp["content"],
                "framework": framework,
                "file_type": file_type,
                "extension": Path(comp["filename"]).suffix.lower(),
                "size": len(comp["content"]),
                "added_at": datetime.utcnow().isoformat(),
            })

        session.components = existing_components
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Added {len(components)} components to session {session_id}")
        return session

    async def start_analysis(self, session_id: int) -> ComponentReferenceSession:
        """
        Start the analysis phase for a session.

        Args:
            session_id: ID of the session

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.components:
            raise ValueError("No components to analyze")

        session.status = "analyzing"
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Started analysis for session {session_id}")
        return session

    async def save_analysis(
        self,
        session_id: int,
        analysis: dict,
    ) -> ComponentReferenceSession:
        """
        Save analysis results and move to planning phase.

        Args:
            session_id: ID of the session
            analysis: Analysis results dict

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Detect target framework
        from lib.framework_detector import detect_framework
        framework_info = detect_framework(self.project_dir)
        session.target_framework = framework_info.identifier

        session.extracted_analysis = analysis
        session.status = "planning"
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Saved analysis for session {session_id}")
        return session

    async def save_plan(
        self,
        session_id: int,
        plan: dict,
    ) -> ComponentReferenceSession:
        """
        Save generation plan and move to generating phase.

        Args:
            session_id: ID of the session
            plan: Generation plan dict

        Returns:
            Updated session
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.generation_plan = plan
        session.status = "generating"
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Saved plan for session {session_id}")
        return session

    async def link_to_feature(
        self,
        session_id: int,
        feature_id: int,
    ) -> Feature:
        """
        Link a component reference session to a feature.

        Args:
            session_id: ID of the component reference session
            feature_id: ID of the feature to link

        Returns:
            Updated feature
        """
        feature = self.db.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            raise ValueError(f"Feature {feature_id} not found")

        feature.reference_session_id = session_id
        self.db.commit()
        self.db.refresh(feature)

        logger.info(f"Linked session {session_id} to feature {feature_id}")
        return feature

    async def get_reference_context(self, feature_id: int) -> Optional[dict]:
        """
        Get the reference context for a feature.

        Returns the analysis and plan from the linked component reference session.

        Args:
            feature_id: ID of the feature

        Returns:
            Dict with analysis and plan, or None if no reference
        """
        feature = self.db.query(Feature).filter(Feature.id == feature_id).first()
        if not feature or not feature.reference_session_id:
            return None

        session = self.db.query(ComponentReferenceSession).filter(
            ComponentReferenceSession.id == feature.reference_session_id
        ).first()

        if not session:
            return None

        return {
            "session_id": session.id,
            "source_type": session.source_type,
            "source_url": session.source_url,
            "analysis": session.extracted_analysis,
            "plan": session.generation_plan,
            "target_framework": session.target_framework,
        }

    async def complete_session(self, session_id: int) -> ComponentReferenceSession:
        """Mark a session as complete."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = "complete"
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Completed component reference session {session_id}")
        return session

    async def fail_session(self, session_id: int, error: str) -> ComponentReferenceSession:
        """Mark a session as failed."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = "failed"
        session.error_message = error
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        logger.error(f"Failed component reference session {session_id}: {error}")
        return session

    async def cancel_session(self, session_id: int) -> bool:
        """Cancel and delete a session."""
        session = await self.get_session(session_id)
        if not session:
            return False

        self.db.delete(session)
        self.db.commit()

        logger.info(f"Cancelled component reference session {session_id}")
        return True
