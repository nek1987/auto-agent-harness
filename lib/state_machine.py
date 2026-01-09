"""
Agent State Machine
===================

Manages agent lifecycle states with valid transitions, checkpoints,
and protection against invalid state changes.

States:
- IDLE: No active work
- INITIALIZING: Reading spec, creating features
- ANALYZING: Analyzing existing codebase to identify features
- PLANNING: Creating execution plan for a feature
- CODING: Implementing a feature
- TESTING: Running tests for implemented feature
- VERIFYING: Verifying feature works correctly
- WAITING_APPROVAL: Waiting for user approval (for critical changes)
- ERROR: An error occurred
- COMPLETED: All features done
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"  # Analyzing existing codebase
    PLANNING = "planning"
    CODING = "coding"
    TESTING = "testing"
    VERIFYING = "verifying"
    WAITING_APPROVAL = "waiting_approval"
    ERROR = "error"
    COMPLETED = "completed"


# Valid state transitions
VALID_TRANSITIONS: dict[AgentState, list[AgentState]] = {
    AgentState.IDLE: [
        AgentState.INITIALIZING,
        AgentState.ANALYZING,  # Can start analysis from idle
        AgentState.CODING,
        AgentState.PLANNING,
    ],
    AgentState.INITIALIZING: [
        AgentState.PLANNING,
        AgentState.CODING,
        AgentState.ERROR,
        AgentState.COMPLETED,
    ],
    AgentState.ANALYZING: [
        AgentState.PLANNING,  # After analysis, plan next steps
        AgentState.CODING,    # Start implementing improvements
        AgentState.COMPLETED, # Analysis finished, no work needed
        AgentState.IDLE,      # Return to idle
        AgentState.ERROR,     # Error during analysis
    ],
    AgentState.PLANNING: [
        AgentState.CODING,
        AgentState.WAITING_APPROVAL,
        AgentState.ERROR,
        AgentState.IDLE,
    ],
    AgentState.CODING: [
        AgentState.TESTING,
        AgentState.ERROR,
        AgentState.IDLE,
    ],
    AgentState.TESTING: [
        AgentState.VERIFYING,
        AgentState.CODING,  # If tests fail, go back to coding
        AgentState.ERROR,
        AgentState.IDLE,
    ],
    AgentState.VERIFYING: [
        AgentState.COMPLETED,
        AgentState.CODING,  # If verification fails
        AgentState.PLANNING,  # Move to next feature
        AgentState.IDLE,
        AgentState.ERROR,
    ],
    AgentState.WAITING_APPROVAL: [
        AgentState.CODING,
        AgentState.PLANNING,
        AgentState.IDLE,
        AgentState.ERROR,
    ],
    AgentState.ERROR: [
        AgentState.IDLE,
        AgentState.CODING,
        AgentState.PLANNING,
    ],
    AgentState.COMPLETED: [
        AgentState.IDLE,
        AgentState.PLANNING,  # For new specs
    ],
}


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: AgentState
    to_state: AgentState
    timestamp: datetime
    feature_id: Optional[int] = None
    reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "feature_id": self.feature_id,
            "reason": self.reason,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StateTransition":
        """Create from dictionary."""
        return cls(
            from_state=AgentState(data["from_state"]),
            to_state=AgentState(data["to_state"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            feature_id=data.get("feature_id"),
            reason=data.get("reason"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentContext:
    """Current agent context and state."""
    state: AgentState = AgentState.IDLE
    current_feature_id: Optional[int] = None
    current_spec: Optional[str] = None
    iteration: int = 0
    max_iterations: int = 1000
    session_id: Optional[str] = None
    started_at: Optional[datetime] = None
    errors: list[str] = field(default_factory=list)
    transitions: list[StateTransition] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "state": self.state.value,
            "current_feature_id": self.current_feature_id,
            "current_spec": self.current_spec,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "errors": self.errors,
            "transitions": [t.to_dict() for t in self.transitions[-100:]],  # Keep last 100
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentContext":
        """Create from dictionary."""
        ctx = cls(
            state=AgentState(data.get("state", "idle")),
            current_feature_id=data.get("current_feature_id"),
            current_spec=data.get("current_spec"),
            iteration=data.get("iteration", 0),
            max_iterations=data.get("max_iterations", 1000),
            session_id=data.get("session_id"),
            errors=data.get("errors", []),
        )
        if data.get("started_at"):
            ctx.started_at = datetime.fromisoformat(data["started_at"])
        ctx.transitions = [
            StateTransition.from_dict(t)
            for t in data.get("transitions", [])
        ]
        return ctx


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, from_state: AgentState, to_state: AgentState):
        self.from_state = from_state
        self.to_state = to_state
        valid = VALID_TRANSITIONS.get(from_state, [])
        super().__init__(
            f"Invalid transition: {from_state.value} → {to_state.value}. "
            f"Valid transitions from {from_state.value}: {[s.value for s in valid]}"
        )


class MaxIterationsError(Exception):
    """Raised when max iterations is reached."""
    def __init__(self, iterations: int, max_iterations: int):
        self.iterations = iterations
        self.max_iterations = max_iterations
        super().__init__(
            f"Max iterations reached: {iterations}/{max_iterations}"
        )


class AgentStateMachine:
    """
    Manages agent state transitions with validation and history.

    Features:
    - Validates state transitions against allowed transitions
    - Maintains transition history
    - Supports callbacks on state changes
    - Persists state to disk
    - Tracks iterations with configurable limit
    """

    def __init__(
        self,
        project_dir: Optional[Path] = None,
        max_iterations: int = 1000,
        on_transition: Optional[Callable[[StateTransition], None]] = None,
    ):
        """
        Initialize the state machine.

        Args:
            project_dir: Project directory for state persistence
            max_iterations: Maximum iterations before auto-stop
            on_transition: Callback function called on each transition
        """
        self.project_dir = project_dir
        self.context = AgentContext(max_iterations=max_iterations)
        self.on_transition = on_transition
        self._state_file: Optional[Path] = None

        if project_dir:
            self._state_file = project_dir / ".agent_state.json"
            self._load_state()

    def _load_state(self) -> None:
        """Load state from disk if available."""
        if self._state_file and self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                self.context = AgentContext.from_dict(data)
                logger.info(f"Loaded agent state: {self.context.state.value}")
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Could not load state file: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        if self._state_file:
            try:
                self._state_file.write_text(
                    json.dumps(self.context.to_dict(), indent=2)
                )
            except OSError as e:
                logger.error(f"Could not save state file: {e}")

    @property
    def state(self) -> AgentState:
        """Get current state."""
        return self.context.state

    @property
    def is_active(self) -> bool:
        """Check if agent is in an active (working) state."""
        return self.context.state in {
            AgentState.INITIALIZING,
            AgentState.ANALYZING,
            AgentState.PLANNING,
            AgentState.CODING,
            AgentState.TESTING,
            AgentState.VERIFYING,
        }

    @property
    def is_idle(self) -> bool:
        """Check if agent is idle."""
        return self.context.state == AgentState.IDLE

    @property
    def is_error(self) -> bool:
        """Check if agent is in error state."""
        return self.context.state == AgentState.ERROR

    @property
    def is_completed(self) -> bool:
        """Check if agent has completed all work."""
        return self.context.state == AgentState.COMPLETED

    def can_transition(self, to_state: AgentState) -> bool:
        """Check if transition to given state is valid."""
        valid_states = VALID_TRANSITIONS.get(self.context.state, [])
        return to_state in valid_states

    def transition(
        self,
        to_state: AgentState,
        feature_id: Optional[int] = None,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        force: bool = False,
    ) -> StateTransition:
        """
        Transition to a new state.

        Args:
            to_state: Target state
            feature_id: Current feature ID (optional)
            reason: Reason for transition (optional)
            metadata: Additional metadata (optional)
            force: Force transition even if invalid (use with caution)

        Returns:
            StateTransition record

        Raises:
            InvalidTransitionError: If transition is not valid
            MaxIterationsError: If max iterations reached
        """
        from_state = self.context.state

        # Validate transition
        if not force and not self.can_transition(to_state):
            raise InvalidTransitionError(from_state, to_state)

        # Check iteration limit
        self.context.iteration += 1
        if self.context.iteration > self.context.max_iterations:
            self.context.state = AgentState.ERROR
            self.context.errors.append(
                f"Max iterations reached: {self.context.iteration}"
            )
            self._save_state()
            raise MaxIterationsError(
                self.context.iteration,
                self.context.max_iterations
            )

        # Create transition record
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.now(timezone.utc),
            feature_id=feature_id or self.context.current_feature_id,
            reason=reason,
            metadata=metadata or {},
        )

        # Update context
        self.context.state = to_state
        if feature_id is not None:
            self.context.current_feature_id = feature_id
        self.context.transitions.append(transition)

        # Set started_at on first active state
        if self.is_active and self.context.started_at is None:
            self.context.started_at = datetime.now(timezone.utc)

        # Save state
        self._save_state()

        # Call callback
        if self.on_transition:
            try:
                self.on_transition(transition)
            except Exception as e:
                logger.error(f"Transition callback error: {e}")

        logger.info(
            f"State transition: {from_state.value} → {to_state.value}"
            f" (feature={feature_id}, reason={reason})"
        )

        return transition

    def record_error(self, error: str, transition_to_error: bool = True) -> None:
        """
        Record an error.

        Args:
            error: Error message
            transition_to_error: Whether to transition to ERROR state
        """
        self.context.errors.append(error)

        if transition_to_error and self.can_transition(AgentState.ERROR):
            self.transition(AgentState.ERROR, reason=error)
        else:
            self._save_state()

    def reset(self) -> None:
        """Reset state machine to initial state."""
        self.context = AgentContext(max_iterations=self.context.max_iterations)
        self._save_state()
        logger.info("State machine reset to IDLE")

    def start_session(self, session_id: Optional[str] = None) -> None:
        """Start a new agent session."""
        if session_id is None:
            session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        self.context.session_id = session_id
        self.context.started_at = datetime.now(timezone.utc)
        self.context.iteration = 0
        self.context.errors = []

        self._save_state()
        logger.info(f"Started session: {session_id}")

    def get_recent_transitions(self, count: int = 10) -> list[StateTransition]:
        """Get recent state transitions."""
        return self.context.transitions[-count:]

    def get_time_in_state(self) -> Optional[float]:
        """Get seconds spent in current state."""
        if not self.context.transitions:
            return None

        last_transition = self.context.transitions[-1]
        return (datetime.now(timezone.utc) - last_transition.timestamp).total_seconds()

    def get_stats(self) -> dict:
        """Get state machine statistics."""
        return {
            "current_state": self.context.state.value,
            "iteration": self.context.iteration,
            "max_iterations": self.context.max_iterations,
            "session_id": self.context.session_id,
            "started_at": self.context.started_at.isoformat() if self.context.started_at else None,
            "error_count": len(self.context.errors),
            "transition_count": len(self.context.transitions),
            "current_feature_id": self.context.current_feature_id,
            "time_in_state": self.get_time_in_state(),
        }
