"""
Library modules for Auto-Agent-Harness.

Contains:
- dependency_resolver: Topological sorting for feature dependencies
- context_loader: Loading context files for agent prompts
- state_machine: Agent lifecycle state management
- loop_detector: Detection of repetitive agent actions
- checkpoint: State snapshots and rollback
- skills_loader: Loading and managing skills from .claude/skills/
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
]
