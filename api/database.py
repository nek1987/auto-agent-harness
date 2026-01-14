"""
Database Models and Connection
==============================

SQLite database schema for feature storage using SQLAlchemy.
"""

from pathlib import Path
from typing import Optional

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker
from sqlalchemy.types import JSON

Base = declarative_base()


class Feature(Base):
    """Feature model representing a test case/feature to implement."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array
    passes = Column(Boolean, default=False, index=True)
    in_progress = Column(Boolean, default=False, index=True)

    # New fields for multi-spec and dependencies support
    source_spec = Column(String(100), default="main", index=True)  # Which spec this feature came from
    dependencies = Column(JSON, nullable=True)  # List of feature IDs this depends on

    # Bug System fields
    item_type = Column(String(20), default="feature", index=True)  # "feature" or "bug"
    parent_bug_id = Column(Integer, nullable=True, index=True)  # For fix features, reference to parent bug
    bug_status = Column(String(20), nullable=True, index=True)  # "open", "analyzing", "fixing", "resolved"

    # Architectural layer for proper implementation ordering
    # 0=skeleton, 1=database, 2=backend_core, 3=auth, 4=backend_features,
    # 5=frontend_core, 6=frontend_features, 7=integration, 8=quality
    arch_layer = Column(Integer, nullable=False, default=8, index=True)

    # Skills Analysis: assigned skills for coding agent to use during implementation
    assigned_skills = Column(JSON, nullable=True)  # List of skill names, e.g., ["senior-backend", "api-designer"]

    # Component Reference: link to a ComponentReferenceSession for using code references
    reference_session_id = Column(Integer, nullable=True, index=True)

    def to_dict(self) -> dict:
        """Convert feature to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "in_progress": self.in_progress,
            "source_spec": self.source_spec,
            "dependencies": self.dependencies,
            "item_type": self.item_type,
            "parent_bug_id": self.parent_bug_id,
            "bug_status": self.bug_status,
            "arch_layer": self.arch_layer,
            "assigned_skills": self.assigned_skills,
            "reference_session_id": self.reference_session_id,
        }


class RedesignSession(Base):
    """
    Redesign session model for tracking frontend redesign operations.

    A redesign session tracks the process of transforming a project's
    design system based on reference images, URLs, or Figma files.
    """

    __tablename__ = "redesign_sessions"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)

    # Session status tracking
    status = Column(
        String(20),
        default="collecting",
        index=True,
        comment="collecting, extracting, planning, approving, implementing, verifying, complete, failed"
    )
    current_phase = Column(
        String(20),
        nullable=True,
        comment="references, tokens, plan, globals, config, components, pages, verification"
    )

    # Reference data - stored as JSON array of reference objects
    # [{type: 'image'|'url'|'figma', data: base64/url, metadata: {...}}]
    references = Column(JSON, nullable=True)

    # Extracted design tokens - follows the design-tokens-v1 schema
    extracted_tokens = Column(JSON, nullable=True)

    # Change plan - files to modify and their changes
    # {phases: [{name, description, files: [{path, action, changes}]}]}
    change_plan = Column(JSON, nullable=True)

    # Detected framework info
    framework_detected = Column(
        String(50),
        nullable=True,
        comment="react-tailwind, vue-css, shadcn, next-tailwind, etc."
    )

    # Error message if failed
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to approvals
    approvals = relationship("RedesignApproval", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert session to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "status": self.status,
            "current_phase": self.current_phase,
            "references": self.references,
            "extracted_tokens": self.extracted_tokens,
            "change_plan": self.change_plan,
            "framework_detected": self.framework_detected,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "approvals": [a.to_dict() for a in self.approvals] if self.approvals else [],
        }


class RedesignApproval(Base):
    """
    Redesign approval model for tracking user approvals at each phase.

    Each phase of the redesign process requires user approval before
    the agent can proceed with implementation.
    """

    __tablename__ = "redesign_approvals"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("redesign_sessions.id"), nullable=False, index=True)

    # Phase this approval is for
    phase = Column(
        String(20),
        nullable=False,
        comment="tokens, plan, globals, config, components, pages, verification"
    )

    # Approval status
    approved = Column(Boolean, default=False)

    # User modifications to the plan (if any)
    # Allows user to adjust tokens or file changes before approval
    modifications = Column(JSON, nullable=True)

    # Optional user comment
    comment = Column(Text, nullable=True)

    # Timestamp
    approved_at = Column(DateTime, nullable=True)

    # Relationship back to session
    session = relationship("RedesignSession", back_populates="approvals")

    def to_dict(self) -> dict:
        """Convert approval to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "phase": self.phase,
            "approved": self.approved,
            "modifications": self.modifications,
            "comment": self.comment,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }


class ComponentReferenceSession(Base):
    """
    Component Reference session for analyzing code components from external sources
    (e.g., v0.dev, shadcn/ui) and using them as references for generating new components.

    Unlike RedesignSession which works with visual references (images/URLs),
    this works with actual code files to extract patterns and structures.
    """

    __tablename__ = "component_reference_sessions"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)

    # Session status tracking
    status = Column(
        String(20),
        default="uploading",
        index=True,
        comment="uploading, analyzing, planning, generating, complete, failed"
    )

    # Source information
    source_type = Column(
        String(20),
        nullable=False,
        default="custom",
        comment="v0, shadcn, custom"
    )
    source_url = Column(String(500), nullable=True)  # Original URL if available (e.g., v0.dev link)

    # Uploaded component files
    # [{filename, content, framework, file_type}]
    components = Column(JSON, nullable=True)

    # Extracted analysis from Claude
    # {
    #   patterns: [{name, description, code_example}],
    #   styling_approach: "tailwind|css-modules|styled-components",
    #   dependencies: ["react-icons", "framer-motion"],
    #   structure: {props_pattern, state_pattern, hooks_used},
    #   design_tokens: {colors, spacing, typography}
    # }
    extracted_analysis = Column(JSON, nullable=True)

    # Generation plan for target project
    # {
    #   target_framework: "react-tailwind",
    #   components_to_create: [{name, based_on, adaptations}],
    #   files_to_create: [{path, purpose}]
    # }
    generation_plan = Column(JSON, nullable=True)

    # Generated components output
    generated_components = Column(JSON, nullable=True)

    # Target framework detected in the project
    target_framework = Column(String(50), nullable=True)

    # Error message if failed
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert session to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "status": self.status,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "components": self.components,
            "extracted_analysis": self.extracted_analysis,
            "generation_plan": self.generation_plan,
            "generated_components": self.generated_components,
            "target_framework": self.target_framework,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def get_database_path(project_dir: Path) -> Path:
    """Return the path to the SQLite database for a project."""
    return project_dir / "features.db"


def get_database_url(project_dir: Path) -> str:
    """Return the SQLAlchemy database URL for a project.

    Uses POSIX-style paths (forward slashes) for cross-platform compatibility.
    """
    db_path = get_database_path(project_dir)
    return f"sqlite:///{db_path.as_posix()}"


def _migrate_database(engine) -> None:
    """Run database migrations for new columns."""
    from sqlalchemy import text

    with engine.connect() as conn:
        # Check existing columns
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        # Migration 1: Add in_progress column
        if "in_progress" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN in_progress BOOLEAN DEFAULT 0"))
            conn.commit()

        # Migration 2: Add source_spec column
        if "source_spec" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN source_spec VARCHAR(100) DEFAULT 'main'"))
            conn.commit()

        # Migration 3: Add dependencies column
        if "dependencies" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN dependencies JSON"))
            conn.commit()

        # Migration 4: Add item_type column for Bug System
        if "item_type" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN item_type VARCHAR(20) DEFAULT 'feature'"))
            conn.commit()

        # Migration 5: Add parent_bug_id column for Bug System
        if "parent_bug_id" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN parent_bug_id INTEGER"))
            conn.commit()

        # Migration 6: Add bug_status column for Bug System
        if "bug_status" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN bug_status VARCHAR(20)"))
            conn.commit()

        # Migration 7: Add arch_layer column for architectural ordering
        if "arch_layer" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN arch_layer INTEGER DEFAULT 8"))
            conn.commit()
            # Create index for better query performance
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_arch_layer ON features(arch_layer)"))
            conn.commit()

        # Migration 8: Add assigned_skills column for skills-based feature analysis
        if "assigned_skills" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN assigned_skills JSON"))
            conn.commit()

        # Migration 9: Add reference_session_id column for Component Reference system
        if "reference_session_id" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN reference_session_id INTEGER"))
            conn.commit()
            # Create index for better query performance
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_reference_session_id ON features(reference_session_id)"))
            conn.commit()


def create_database(project_dir: Path) -> tuple:
    """
    Create database and return engine + session maker.

    Args:
        project_dir: Directory containing the project

    Returns:
        Tuple of (engine, SessionLocal)
    """
    db_url = get_database_url(project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    # Run migrations for existing databases
    _migrate_database(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


# Global session maker - will be set when server starts
_session_maker: Optional[sessionmaker] = None


def set_session_maker(session_maker: sessionmaker) -> None:
    """Set the global session maker."""
    global _session_maker
    _session_maker = session_maker


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session.

    Yields a database session and ensures it's closed after use.
    """
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call set_session_maker first.")

    db = _session_maker()
    try:
        yield db
    finally:
        db.close()
