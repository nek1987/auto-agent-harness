"""
Library modules for Auto-Agent-Harness.

Contains:
- dependency_resolver: Topological sorting for feature dependencies
- context_loader: Loading context files for agent prompts
- state_machine: Agent lifecycle state management
- loop_detector: Detection of repetitive agent actions
- checkpoint: State snapshots and rollback
- skills_loader: Loading and managing skills from .claude/skills/
- error_classifier: Error classification and user-friendly messages
- failure_tracker: Consecutive failure tracking with auto-pause
"""

from .dependency_resolver import DependencyResolver, DependencyCycleError
from .context_loader import load_context_files, get_context_files, ContextFile
from .skills_loader import SkillsLoader, SkillInfo, get_skills_context, SKILL_CATEGORIES
from .state_machine import (
    AgentState,
    AgentStateMachine,
    AgentContext,
    StateTransition,
    InvalidTransitionError,
    MaxIterationsError,
)
from .loop_detector import LoopDetector, LoopPattern, Action, create_action_from_tool_call
from .checkpoint import CheckpointManager, Checkpoint, CheckpointError, auto_checkpoint
from .error_classifier import (
    ErrorType,
    ErrorInfo,
    classify_error,
    get_user_friendly_message,
    get_error_message,
    is_rate_limit_error,
    is_quota_exhausted_error,
    is_authentication_error,
    extract_retry_after,
)
from .failure_tracker import (
    FailureTracker,
    FailureRecord,
    FailureStats,
    FAILURE_WINDOW_SECONDS,
    CONSECUTIVE_FAILURE_THRESHOLD,
)

__all__ = [
    # Dependency resolver
    "DependencyResolver",
    "DependencyCycleError",
    # Context loader
    "load_context_files",
    "get_context_files",
    "ContextFile",
    # Skills loader
    "SkillsLoader",
    "SkillInfo",
    "get_skills_context",
    "SKILL_CATEGORIES",
    # State machine
    "AgentState",
    "AgentStateMachine",
    "AgentContext",
    "StateTransition",
    "InvalidTransitionError",
    "MaxIterationsError",
    # Loop detector
    "LoopDetector",
    "LoopPattern",
    "Action",
    "create_action_from_tool_call",
    # Checkpoint
    "CheckpointManager",
    "Checkpoint",
    "CheckpointError",
    "auto_checkpoint",
    # Error classifier
    "ErrorType",
    "ErrorInfo",
    "classify_error",
    "get_user_friendly_message",
    "get_error_message",
    "is_rate_limit_error",
    "is_quota_exhausted_error",
    "is_authentication_error",
    "extract_retry_after",
    # Failure tracker
    "FailureTracker",
    "FailureRecord",
    "FailureStats",
    "FAILURE_WINDOW_SECONDS",
    "CONSECUTIVE_FAILURE_THRESHOLD",
]
