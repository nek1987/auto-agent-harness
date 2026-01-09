"""
Checkpoint Manager
==================

Creates and manages checkpoints for agent state recovery.

Checkpoints include:
- Git commit snapshot
- Features database state
- Agent context state
- Timestamp and metadata

Supports:
- Creating checkpoints at key moments
- Rolling back to previous checkpoints
- Listing available checkpoints
- Automatic cleanup of old checkpoints
"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """Represents a checkpoint."""
    id: str
    name: str
    created_at: datetime
    git_commit: Optional[str] = None
    feature_id: Optional[int] = None
    feature_count: int = 0
    features_passing: int = 0
    agent_state: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "git_commit": self.git_commit,
            "feature_id": self.feature_id,
            "feature_count": self.feature_count,
            "features_passing": self.features_passing,
            "agent_state": self.agent_state,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            git_commit=data.get("git_commit"),
            feature_id=data.get("feature_id"),
            feature_count=data.get("feature_count", 0),
            features_passing=data.get("features_passing", 0),
            agent_state=data.get("agent_state"),
            metadata=data.get("metadata", {}),
        )


class CheckpointError(Exception):
    """Error during checkpoint operations."""
    pass


class CheckpointManager:
    """
    Manages checkpoints for state recovery.

    Features:
    - Git-based file snapshots
    - Database state backup
    - Rollback capability
    - Automatic cleanup
    """

    def __init__(
        self,
        project_dir: Path,
        max_checkpoints: int = 20,
        checkpoint_dir_name: str = ".checkpoints",
    ):
        """
        Initialize checkpoint manager.

        Args:
            project_dir: Project directory
            max_checkpoints: Maximum checkpoints to keep
            checkpoint_dir_name: Name of checkpoints directory
        """
        self.project_dir = Path(project_dir)
        self.max_checkpoints = max_checkpoints
        self.checkpoint_dir = self.project_dir / checkpoint_dir_name
        self.manifest_file = self.checkpoint_dir / "manifest.json"

        # Ensure checkpoint directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Load manifest
        self._checkpoints: list[Checkpoint] = []
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load checkpoints manifest."""
        if self.manifest_file.exists():
            try:
                data = json.loads(self.manifest_file.read_text())
                self._checkpoints = [
                    Checkpoint.from_dict(cp) for cp in data.get("checkpoints", [])
                ]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Could not load checkpoint manifest: {e}")
                self._checkpoints = []

    def _save_manifest(self) -> None:
        """Save checkpoints manifest."""
        data = {
            "version": "1.0",
            "checkpoints": [cp.to_dict() for cp in self._checkpoints],
        }
        self.manifest_file.write_text(json.dumps(data, indent=2))

    def _generate_checkpoint_id(self, name: str) -> str:
        """Generate unique checkpoint ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        # Sanitize name
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return f"{safe_name}_{timestamp}"

    def _is_git_repo(self) -> bool:
        """Check if project is a git repository."""
        git_dir = self.project_dir / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def _get_current_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        if not self._is_git_repo():
            return None

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def _create_git_checkpoint(self, checkpoint_id: str, message: str) -> Optional[str]:
        """Create git commit for checkpoint."""
        if not self._is_git_repo():
            return None

        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.project_dir,
                capture_output=True,
                timeout=30,
            )

            # Create commit
            result = subprocess.run(
                ["git", "commit", "-m", f"Checkpoint: {message}", "--allow-empty"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return self._get_current_commit()

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Could not create git checkpoint: {e}")

        return None

    def _backup_features_db(self, checkpoint_id: str) -> Optional[Path]:
        """Backup features database."""
        features_db = self.project_dir / "features.db"
        if not features_db.exists():
            return None

        backup_path = self.checkpoint_dir / checkpoint_id / "features.db"
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(features_db, backup_path)
            return backup_path
        except OSError as e:
            logger.warning(f"Could not backup features.db: {e}")
            return None

    def _get_features_stats(self) -> tuple[int, int]:
        """Get feature count and passing count."""
        features_db = self.project_dir / "features.db"
        if not features_db.exists():
            return 0, 0

        try:
            import sqlite3
            conn = sqlite3.connect(str(features_db))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM features")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM features WHERE passes = 1")
            passing = cursor.fetchone()[0]

            conn.close()
            return total, passing
        except Exception:
            return 0, 0

    def create(
        self,
        name: str,
        feature_id: Optional[int] = None,
        agent_state: Optional[str] = None,
        metadata: Optional[dict] = None,
        create_git_commit: bool = True,
    ) -> Checkpoint:
        """
        Create a new checkpoint.

        Args:
            name: Checkpoint name/description
            feature_id: Current feature being worked on
            agent_state: Current agent state
            metadata: Additional metadata
            create_git_commit: Whether to create git commit

        Returns:
            Created checkpoint
        """
        checkpoint_id = self._generate_checkpoint_id(name)

        # Get git commit
        git_commit = None
        if create_git_commit:
            git_commit = self._create_git_checkpoint(checkpoint_id, name)
        else:
            git_commit = self._get_current_commit()

        # Backup features database
        self._backup_features_db(checkpoint_id)

        # Get features stats
        feature_count, features_passing = self._get_features_stats()

        # Create checkpoint object
        checkpoint = Checkpoint(
            id=checkpoint_id,
            name=name,
            created_at=datetime.now(timezone.utc),
            git_commit=git_commit,
            feature_id=feature_id,
            feature_count=feature_count,
            features_passing=features_passing,
            agent_state=agent_state,
            metadata=metadata or {},
        )

        # Save agent state to checkpoint directory
        if agent_state:
            state_file = self.checkpoint_dir / checkpoint_id / "agent_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps({"state": agent_state}))

        # Add to manifest
        self._checkpoints.append(checkpoint)
        self._save_manifest()

        # Cleanup old checkpoints
        self._cleanup_old_checkpoints()

        logger.info(f"Created checkpoint: {checkpoint_id}")
        return checkpoint

    def rollback(self, checkpoint_id: str, restore_git: bool = True) -> bool:
        """
        Rollback to a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to restore
            restore_git: Whether to restore git state

        Returns:
            True if successful
        """
        # Find checkpoint
        checkpoint = self.get(checkpoint_id)
        if not checkpoint:
            raise CheckpointError(f"Checkpoint not found: {checkpoint_id}")

        checkpoint_path = self.checkpoint_dir / checkpoint_id

        # Restore git state
        if restore_git and checkpoint.git_commit and self._is_git_repo():
            try:
                subprocess.run(
                    ["git", "reset", "--hard", checkpoint.git_commit],
                    cwd=self.project_dir,
                    capture_output=True,
                    timeout=30,
                    check=True,
                )
                logger.info(f"Restored git to commit: {checkpoint.git_commit}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to restore git: {e}")
                return False

        # Restore features database
        backup_db = checkpoint_path / "features.db"
        if backup_db.exists():
            target_db = self.project_dir / "features.db"
            try:
                shutil.copy2(backup_db, target_db)
                logger.info("Restored features.db")
            except OSError as e:
                logger.error(f"Failed to restore features.db: {e}")
                return False

        logger.info(f"Rolled back to checkpoint: {checkpoint_id}")
        return True

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        for cp in self._checkpoints:
            if cp.id == checkpoint_id:
                return cp
        return None

    def list(self, limit: int = 10) -> list[Checkpoint]:
        """List recent checkpoints."""
        return sorted(
            self._checkpoints,
            key=lambda cp: cp.created_at,
            reverse=True,
        )[:limit]

    def get_latest(self) -> Optional[Checkpoint]:
        """Get most recent checkpoint."""
        if not self._checkpoints:
            return None
        return max(self._checkpoints, key=lambda cp: cp.created_at)

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        checkpoint = self.get(checkpoint_id)
        if not checkpoint:
            return False

        # Remove checkpoint directory
        checkpoint_path = self.checkpoint_dir / checkpoint_id
        if checkpoint_path.exists():
            try:
                shutil.rmtree(checkpoint_path)
            except OSError as e:
                logger.warning(f"Could not delete checkpoint directory: {e}")

        # Remove from manifest
        self._checkpoints = [cp for cp in self._checkpoints if cp.id != checkpoint_id]
        self._save_manifest()

        logger.info(f"Deleted checkpoint: {checkpoint_id}")
        return True

    def _cleanup_old_checkpoints(self) -> None:
        """Remove old checkpoints exceeding max limit."""
        if len(self._checkpoints) <= self.max_checkpoints:
            return

        # Sort by date, oldest first
        sorted_checkpoints = sorted(
            self._checkpoints,
            key=lambda cp: cp.created_at,
        )

        # Delete oldest checkpoints
        to_delete = sorted_checkpoints[:-self.max_checkpoints]
        for cp in to_delete:
            self.delete(cp.id)

        logger.info(f"Cleaned up {len(to_delete)} old checkpoints")

    def get_stats(self) -> dict:
        """Get checkpoint statistics."""
        return {
            "total_checkpoints": len(self._checkpoints),
            "max_checkpoints": self.max_checkpoints,
            "checkpoint_dir": str(self.checkpoint_dir),
            "latest": self.get_latest().to_dict() if self.get_latest() else None,
        }


def auto_checkpoint(
    checkpoint_manager: CheckpointManager,
    name: str,
    feature_id: Optional[int] = None,
    agent_state: Optional[str] = None,
) -> Checkpoint:
    """
    Create an automatic checkpoint.

    Convenience function for creating checkpoints at key points.

    Args:
        checkpoint_manager: CheckpointManager instance
        name: Checkpoint name
        feature_id: Current feature ID
        agent_state: Current agent state

    Returns:
        Created checkpoint
    """
    return checkpoint_manager.create(
        name=name,
        feature_id=feature_id,
        agent_state=agent_state,
        metadata={
            "auto": True,
            "trigger": name,
        },
    )
