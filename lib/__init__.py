"""
Library modules for Auto-Agent-Harness.

Contains:
- architecture_layers: Architectural layer definitions for implementation ordering
- layer_validator: Validation of feature layer dependencies
- dependency_resolver: Topological sorting for feature dependencies
- context_loader: Loading context files for agent prompts
- state_machine: Agent lifecycle state management
- loop_detector: Detection of repetitive agent actions
- checkpoint: State snapshots and rollback
- skills_loader: Loading and managing skills from .claude/skills/
- error_classifier: Error classification and user-friendly messages
- failure_tracker: Consecutive failure tracking with auto-pause
- project_detector: Auto-detection of project type (Python, Node, Go, etc.)
- project_scaffold: Docker scaffolding for projects
- docker_validator: Validation of Docker configuration
- browser_check: Playwright browser installation check
"""

from .architecture_layers import (
    ArchLayer,
    CATEGORY_TO_LAYER,
    LAYER_NAMES,
    get_layer_for_category,
    get_layer_name,
    get_required_layers,
    is_layer_blocked,
    suggest_next_layer,
)
from .layer_validator import (
    LayerStats,
    LayerValidationResult,
    validate_feature_order,
    get_layer_stats,
    get_blocking_layers,
    validate_layer_dependencies,
    suggest_skip_reason,
    get_layer_progress_summary,
    auto_assign_layer,
)
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
from .project_detector import (
    ProjectTypeInfo,
    detect_project_type,
    detect_language,
    detect_framework,
    get_project_type_string,
    should_use_docker_prompt,
)
from .project_scaffold import (
    scaffold_docker_project,
    ensure_docker_config,
    get_compose_services,
)
from .docker_validator import (
    ValidationResult,
    validate_docker_project,
    find_compose_file,
    find_dockerfiles,
    cleanup_docker_resources,
)
from .browser_check import (
    check_playwright_browser,
    install_playwright_browser,
    ensure_browser_available,
)

__all__ = [
    # Architecture layers
    "ArchLayer",
    "CATEGORY_TO_LAYER",
    "LAYER_NAMES",
    "get_layer_for_category",
    "get_layer_name",
    "get_required_layers",
    "is_layer_blocked",
    "suggest_next_layer",
    # Layer validator
    "LayerStats",
    "LayerValidationResult",
    "validate_feature_order",
    "get_layer_stats",
    "get_blocking_layers",
    "validate_layer_dependencies",
    "suggest_skip_reason",
    "get_layer_progress_summary",
    "auto_assign_layer",
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
    # Project detector
    "ProjectTypeInfo",
    "detect_project_type",
    "detect_language",
    "detect_framework",
    "get_project_type_string",
    "should_use_docker_prompt",
    # Project scaffold
    "scaffold_docker_project",
    "ensure_docker_config",
    "get_compose_services",
    # Docker validator
    "ValidationResult",
    "validate_docker_project",
    "find_compose_file",
    "find_dockerfiles",
    "cleanup_docker_resources",
    # Browser check
    "check_playwright_browser",
    "install_playwright_browser",
    "ensure_browser_available",
]
