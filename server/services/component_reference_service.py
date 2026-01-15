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

from api.database import (
    ComponentReferenceSession,
    Feature,
    PageReference,
    ProjectPageStructure,
)
from lib.page_detector import PageDetector, match_feature_to_page_reference

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

    # ========================================================================
    # Multi-Page Reference Methods
    # ========================================================================

    async def scan_project_pages(self) -> dict:
        """
        Scan the project and detect all pages/routes.

        Returns:
            Dict with detected pages, layouts, and framework info
        """
        detector = PageDetector()
        result = detector.scan(self.project_dir)

        return {
            "framework_type": result.framework_type,
            "pages": [p.to_dict() for p in result.pages],
            "layouts": [l.to_dict() for l in result.layouts],
            "total_pages": len(result.pages),
            "total_layouts": len(result.layouts),
        }

    async def cache_project_pages(self, project_name: str) -> list[ProjectPageStructure]:
        """
        Scan project pages and cache them in the database.

        Args:
            project_name: Name of the project

        Returns:
            List of cached ProjectPageStructure entries
        """
        # Clear existing cache for this project
        self.db.query(ProjectPageStructure).filter(
            ProjectPageStructure.project_name == project_name
        ).delete()

        # Scan project
        detector = PageDetector()
        result = detector.scan(self.project_dir)

        cached = []
        for page in result.pages + result.layouts:
            entry = ProjectPageStructure(
                project_name=project_name,
                element_type=page.element_type,
                file_path=page.file_path,
                route=page.route,
                element_name=page.element_name,
                framework_type=page.framework_type,
                last_scanned_at=datetime.utcnow(),
            )
            self.db.add(entry)
            cached.append(entry)

        self.db.commit()
        logger.info(f"Cached {len(cached)} pages for project {project_name}")
        return cached

    async def list_page_references(self, project_name: str) -> list[PageReference]:
        """
        List all page references for a project.

        Args:
            project_name: Name of the project

        Returns:
            List of PageReference instances
        """
        return (
            self.db.query(PageReference)
            .filter(PageReference.project_name == project_name)
            .order_by(PageReference.page_identifier)
            .all()
        )

    async def get_page_reference(
        self,
        project_name: str,
        page_identifier: str,
    ) -> Optional[PageReference]:
        """
        Get a specific page reference.

        Args:
            project_name: Name of the project
            page_identifier: The page route/identifier

        Returns:
            PageReference if found, None otherwise
        """
        return (
            self.db.query(PageReference)
            .filter(
                PageReference.project_name == project_name,
                PageReference.page_identifier == page_identifier,
            )
            .first()
        )

    async def create_page_reference(
        self,
        project_name: str,
        page_identifier: str,
        session_id: int,
        display_name: Optional[str] = None,
        match_keywords: Optional[list[str]] = None,
        page_type: str = "page",
    ) -> PageReference:
        """
        Create a new page reference linking a page to a session.

        Args:
            project_name: Name of the project
            page_identifier: The page route (e.g., '/dashboard')
            session_id: ID of the ComponentReferenceSession
            display_name: Human-readable name
            match_keywords: Keywords for auto-matching
            page_type: Type of page element

        Returns:
            Created PageReference
        """
        # Check if reference already exists
        existing = await self.get_page_reference(project_name, page_identifier)
        if existing:
            # Update existing reference
            existing.reference_session_id = session_id
            if display_name:
                existing.display_name = display_name
            if match_keywords:
                existing.match_keywords = match_keywords
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            logger.info(f"Updated page reference for {page_identifier}")
            return existing

        # Create new reference
        ref = PageReference(
            project_name=project_name,
            page_type=page_type,
            page_identifier=page_identifier,
            reference_session_id=session_id,
            display_name=display_name or page_identifier.strip("/").replace("/", " ").title() + " Page",
            match_keywords=match_keywords or [],
            auto_match_enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(ref)
        self.db.commit()
        self.db.refresh(ref)

        logger.info(f"Created page reference for {page_identifier} linked to session {session_id}")
        return ref

    async def create_session_for_page(
        self,
        project_name: str,
        page_identifier: str,
        source_type: str = "custom",
        source_url: Optional[str] = None,
        display_name: Optional[str] = None,
        match_keywords: Optional[list[str]] = None,
    ) -> tuple[ComponentReferenceSession, PageReference]:
        """
        Create a new session and page reference in one operation.

        Args:
            project_name: Name of the project
            page_identifier: The page route (e.g., '/dashboard')
            source_type: Source type ('v0', 'shadcn', 'custom')
            source_url: Original URL if available
            display_name: Human-readable name
            match_keywords: Keywords for auto-matching

        Returns:
            Tuple of (session, page_reference)
        """
        # Create session
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
        self.db.flush()  # Get session.id

        # Create page reference
        ref = await self.create_page_reference(
            project_name=project_name,
            page_identifier=page_identifier,
            session_id=session.id,
            display_name=display_name,
            match_keywords=match_keywords,
        )

        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Created session {session.id} and page reference for {page_identifier}")
        return session, ref

    async def get_auto_reference_for_feature(
        self,
        project_name: str,
        feature_id: int,
    ) -> Optional[dict]:
        """
        Get the best matching page reference for a feature using auto-matching.

        Priority:
        1. Direct page_reference_id link on feature
        2. Auto-match based on category/name/description

        Args:
            project_name: Name of the project
            feature_id: ID of the feature

        Returns:
            Dict with reference data and analysis, or None
        """
        feature = self.db.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return None

        # 1. Check direct page_reference_id link
        if feature.page_reference_id:
            ref = self.db.query(PageReference).filter(
                PageReference.id == feature.page_reference_id
            ).first()
            if ref:
                result = {
                    "match_type": "direct_link",
                    "page_reference": ref.to_dict(),
                }

                # Add session analysis if available
                if ref.reference_session_id:
                    session = self.db.query(ComponentReferenceSession).filter(
                        ComponentReferenceSession.id == ref.reference_session_id
                    ).first()
                    if session:
                        result["analysis"] = session.extracted_analysis
                        result["plan"] = session.generation_plan
                        result["target_framework"] = session.target_framework

                return result

        # 2. Auto-match based on feature content
        refs = (
            self.db.query(PageReference)
            .filter(
                PageReference.project_name == project_name,
                PageReference.auto_match_enabled == True,
            )
            .all()
        )

        if not refs:
            return None

        ref_dicts = [r.to_dict() for r in refs]
        matched = match_feature_to_page_reference(
            feature.category or "",
            feature.name or "",
            feature.description or "",
            ref_dicts,
        )

        if not matched:
            return None

        result = {
            "match_type": "auto_matched",
            "page_reference": matched,
        }

        # Get session data for the matched reference
        ref = self.db.query(PageReference).filter(
            PageReference.id == matched["id"]
        ).first()

        if ref and ref.reference_session_id:
            session = self.db.query(ComponentReferenceSession).filter(
                ComponentReferenceSession.id == ref.reference_session_id
            ).first()
            if session:
                result["analysis"] = session.extracted_analysis
                result["plan"] = session.generation_plan
                result["target_framework"] = session.target_framework

        return result

    async def link_feature_to_page_reference(
        self,
        feature_id: int,
        page_reference_id: int,
    ) -> Feature:
        """
        Link a feature directly to a page reference.

        Args:
            feature_id: ID of the feature
            page_reference_id: ID of the page reference

        Returns:
            Updated feature
        """
        feature = self.db.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            raise ValueError(f"Feature {feature_id} not found")

        ref = self.db.query(PageReference).filter(
            PageReference.id == page_reference_id
        ).first()
        if not ref:
            raise ValueError(f"PageReference {page_reference_id} not found")

        feature.page_reference_id = page_reference_id
        self.db.commit()
        self.db.refresh(feature)

        logger.info(f"Linked feature {feature_id} to page reference {page_reference_id}")
        return feature

    async def delete_page_reference(
        self,
        project_name: str,
        page_identifier: str,
    ) -> bool:
        """
        Delete a page reference.

        Args:
            project_name: Name of the project
            page_identifier: The page route/identifier

        Returns:
            True if deleted, False if not found
        """
        ref = await self.get_page_reference(project_name, page_identifier)
        if not ref:
            return False

        # Clear feature links
        self.db.query(Feature).filter(
            Feature.page_reference_id == ref.id
        ).update({"page_reference_id": None})

        self.db.delete(ref)
        self.db.commit()

        logger.info(f"Deleted page reference for {page_identifier}")
        return True

    async def link_to_redesign_session(
        self,
        component_session_id: int,
        redesign_session_id: int,
    ) -> int:
        """
        Link this component session to a redesign session.

        This allows ZIP component uploads to be used for design token extraction
        in the redesign workflow.

        Args:
            component_session_id: ID of the ComponentReferenceSession
            redesign_session_id: ID of the RedesignSession to link to

        Returns:
            The redesign_session_id if successful

        Raises:
            ValueError: If redesign session not found
        """
        from api.database import RedesignSession

        redesign_session = self.db.query(RedesignSession).filter(
            RedesignSession.id == redesign_session_id
        ).first()

        if not redesign_session:
            raise ValueError(f"RedesignSession {redesign_session_id} not found")

        redesign_session.component_session_id = component_session_id
        redesign_session.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(
            f"Linked component session {component_session_id} "
            f"to redesign session {redesign_session_id}"
        )
        return redesign_session_id

    # ========================================================================
    # AI-Driven Feature Generation
    # ========================================================================

    async def ai_analyze_components_for_features(
        self,
        session: ComponentReferenceSession,
    ) -> dict:
        """
        Use Claude to analyze all components and generate a comprehensive feature list.

        Analyzes ALL files in the session (not just "component" types) and uses
        AI to identify logical components, patterns, and generate implementation
        features with dependencies.

        Args:
            session: ComponentReferenceSession with components to analyze

        Returns:
            {
                "identified_components": [...],
                "suggested_features": [
                    {
                        "name": "Feature name",
                        "description": "What this feature does",
                        "steps": ["Step 1", "Step 2", ...],
                        "dependencies": [],
                        "source_files": ["file1.tsx", "file2.ts"],
                        "category": "category-name",
                        "arch_layer": 1-6
                    }
                ],
                "analysis_summary": "..."
            }
        """
        if not session.components:
            return self._fallback_feature_generation([])

        # Prepare file summaries for AI (truncate content to avoid token limits)
        file_summaries = []
        for comp in session.components:
            content = comp.get("content", "")
            # Truncate to first 500 chars for summary
            preview = content[:500] + "..." if len(content) > 500 else content

            file_summaries.append({
                "filename": comp.get("filename", "unknown"),
                "filepath": comp.get("filepath", ""),
                "file_type": comp.get("file_type", "unknown"),
                "framework": comp.get("framework", "unknown"),
                "size": comp.get("size", 0),
                "preview": preview,
            })

        # Build the AI prompt
        prompt = self._build_feature_analysis_prompt(file_summaries)

        try:
            # Call Claude API
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse JSON response
            response_text = response.content[0].text
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end]
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end]

            result = json.loads(response_text.strip())
            logger.info(
                f"AI generated {len(result.get('suggested_features', []))} features "
                f"from {len(session.components)} files"
            )
            return result

        except Exception as e:
            logger.warning(f"AI analysis failed, using fallback: {e}")
            return self._fallback_feature_generation(session.components)

    def _build_feature_analysis_prompt(self, file_summaries: list[dict]) -> str:
        """Build the AI prompt for feature analysis."""
        files_description = "\n".join([
            f"- {f['filename']} ({f['file_type']}, {f['framework']}, {f['size']} bytes)\n"
            f"  Preview: {f['preview'][:200]}..."
            for f in file_summaries[:50]  # Limit to 50 files to avoid token limits
        ])

        return f"""You are analyzing {len(file_summaries)} files from a reference codebase.
Your task is to understand the component structure and generate a comprehensive feature list
for implementing similar functionality in a new project.

## Files to analyze:
{files_description}

## Requirements:
1. Generate **at least 5 features, ideally 8-15 features**
2. Features should be ordered by implementation dependency (foundational first)
3. Each feature should be:
   - Focused (one logical unit of work)
   - Testable (clear completion criteria)
   - Linked to relevant source files from the reference
4. Include dependencies between features (feature index, 0-based)
5. Assign appropriate arch_layer:
   - 1: Infrastructure/Config
   - 2: Data/API Layer
   - 3: Business Logic
   - 4: Hooks/State
   - 5: UI Components
   - 6: Pages/Views

## Output JSON format (return ONLY valid JSON):
{{
    "identified_components": [
        {{"name": "ComponentName", "type": "ui-component|hook|utility|page", "files": ["file1.tsx"]}}
    ],
    "suggested_features": [
        {{
            "name": "Set up design system and theme",
            "description": "Create the foundational design tokens, colors, typography, and spacing system",
            "steps": [
                "Create theme configuration file",
                "Define color palette variables",
                "Set up typography scale",
                "Create spacing system"
            ],
            "dependencies": [],
            "source_files": ["theme.ts", "colors.ts"],
            "category": "infrastructure",
            "arch_layer": 1
        }},
        {{
            "name": "Create base UI primitives",
            "description": "Implement foundational UI components like Button, Input, Card",
            "steps": [
                "Create Button component with variants",
                "Create Input component with validation",
                "Create Card component with styling"
            ],
            "dependencies": [0],
            "source_files": ["Button.tsx", "Input.tsx", "Card.tsx"],
            "category": "ui-components",
            "arch_layer": 5
        }}
    ],
    "analysis_summary": "Brief summary of what was found in the reference code"
}}

Analyze the files and return ONLY the JSON response, no additional text."""

    def _fallback_feature_generation(self, components: list) -> dict:
        """
        Generate features without AI when API is unavailable.

        Uses heuristics based on file structure and naming patterns.

        Args:
            components: List of component dicts from session

        Returns:
            Dict with suggested_features in same format as AI analysis
        """
        from collections import defaultdict

        if not components:
            return {
                "identified_components": [],
                "suggested_features": [],
                "analysis_summary": "No components found to analyze",
            }

        # Group files by category based on path and naming
        by_category = defaultdict(list)

        for comp in components:
            filepath = comp.get("filepath", comp.get("filename", ""))
            filename = comp.get("filename", "")
            file_type = comp.get("file_type", "")

            # Categorize by path patterns
            filepath_lower = filepath.lower()
            if "/components/" in filepath_lower or file_type == "component":
                if any(x in filepath_lower for x in ["ui/", "primitives/", "common/"]):
                    by_category["ui-primitives"].append(comp)
                elif any(x in filepath_lower for x in ["form", "input", "select"]):
                    by_category["form-components"].append(comp)
                elif any(x in filepath_lower for x in ["layout", "nav", "sidebar", "header"]):
                    by_category["layout"].append(comp)
                else:
                    by_category["feature-components"].append(comp)
            elif "/hooks/" in filepath_lower or file_type == "hook" or filename.startswith("use"):
                by_category["hooks"].append(comp)
            elif "/pages/" in filepath_lower or "/views/" in filepath_lower or "/app/" in filepath_lower:
                by_category["pages"].append(comp)
            elif file_type == "styles" or any(x in filepath_lower for x in [".css", ".scss", "theme", "style"]):
                by_category["styles"].append(comp)
            elif file_type == "types" or "types" in filepath_lower or "interface" in filepath_lower:
                by_category["types"].append(comp)
            elif file_type == "utility" or any(x in filepath_lower for x in ["util", "helper", "lib"]):
                by_category["utilities"].append(comp)
            else:
                by_category["other"].append(comp)

        # Generate features from categories
        features = []
        feature_index = 0

        # Define category order and templates
        category_templates = [
            ("styles", "Set up design system and styling", "infrastructure", 1, []),
            ("types", "Define TypeScript types and interfaces", "infrastructure", 1, []),
            ("utilities", "Create utility functions and helpers", "infrastructure", 2, [0, 1]),
            ("hooks", "Implement custom React hooks", "hooks", 4, [0, 1, 2]),
            ("ui-primitives", "Create base UI components", "ui-components", 5, [0]),
            ("form-components", "Implement form components", "ui-components", 5, [0, 4]),
            ("layout", "Build layout and navigation", "layout", 5, [0, 4]),
            ("feature-components", "Create feature components", "features", 5, [0, 4, 5]),
            ("pages", "Implement pages and views", "pages", 6, [0, 4, 6, 7]),
        ]

        for cat_key, name_template, category, arch_layer, dep_indices in category_templates:
            if cat_key not in by_category:
                continue

            files = by_category[cat_key]
            if not files:
                continue

            # Create steps from files
            steps = []
            for f in files[:5]:  # Limit to 5 files per step list
                fname = f.get("filename", "unknown")
                steps.append(f"Implement {fname.replace('.tsx', '').replace('.ts', '')}")

            if len(files) > 5:
                steps.append(f"... and {len(files) - 5} more files")

            # Adjust dependencies to valid indices
            valid_deps = [d for d in dep_indices if d < feature_index]

            features.append({
                "name": name_template,
                "description": f"Create {len(files)} {cat_key.replace('-', ' ')} based on reference code",
                "steps": steps,
                "dependencies": valid_deps,
                "source_files": [f.get("filename", "") for f in files],
                "category": category,
                "arch_layer": arch_layer,
            })
            feature_index += 1

        # Ensure minimum 5 features by splitting large categories if needed
        if len(features) < 5 and by_category:
            # Add generic "other" feature if we have ungrouped files
            if "other" in by_category and by_category["other"]:
                files = by_category["other"]
                features.append({
                    "name": "Implement additional components",
                    "description": f"Create {len(files)} additional components from reference",
                    "steps": [f"Implement {f.get('filename', 'unknown')}" for f in files[:5]],
                    "dependencies": [0] if features else [],
                    "source_files": [f.get("filename", "") for f in files],
                    "category": "components",
                    "arch_layer": 5,
                })

        # Build identified components list
        identified = []
        for comp in components:
            identified.append({
                "name": comp.get("filename", "").replace(".tsx", "").replace(".ts", ""),
                "type": comp.get("file_type", "unknown"),
                "files": [comp.get("filename", "")],
            })

        return {
            "identified_components": identified[:50],  # Limit to 50
            "suggested_features": features,
            "analysis_summary": (
                f"Fallback analysis: Found {len(components)} files, "
                f"generated {len(features)} features across {len(by_category)} categories"
            ),
        }
