"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.

Updated for Claude Code v2.1.1 / SDK 0.1.19 features:
- Enhanced hooks (PostToolUse, SessionStart, SessionEnd)
- Improved tool logging
- Skills integration via setting_sources

Security enhancements:
- Environment variable allowlist for MCP servers (prevents credential leakage)
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import HookMatcher

from security import bash_security_hook


# ============================================================================
# Environment Allowlist (Security)
# ============================================================================

# Only these environment variables are passed to MCP servers
# This prevents credential leakage from parent process
ALLOWED_MCP_ENV_VARS = frozenset([
    # Required for Claude SDK
    "ANTHROPIC_API_KEY",
    # System paths
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    # Locale settings
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    # Terminal settings
    "TERM",
    "COLORTERM",
    # Python-specific
    "PYTHONPATH",
    "PYTHONIOENCODING",
    # Project-specific (added dynamically)
    "PROJECT_DIR",
])


def build_safe_mcp_env(extra_vars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Build a safe environment dictionary for MCP servers.

    Only includes variables from the allowlist plus any explicitly
    provided extra variables. This prevents accidental credential
    leakage from the parent process environment.

    Args:
        extra_vars: Additional variables to include (e.g., PROJECT_DIR)

    Returns:
        Dictionary of safe environment variables
    """
    env = {}

    # Add allowed variables from current environment
    for key in ALLOWED_MCP_ENV_VARS:
        if key in os.environ:
            env[key] = os.environ[key]

    # Add explicit extra variables
    if extra_vars:
        env.update(extra_vars)

    return env

# Logger for tool execution tracking
logger = logging.getLogger(__name__)

# Feature MCP tools for feature/test management
FEATURE_MCP_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_next",
    "mcp__features__feature_get_for_regression",
    "mcp__features__feature_mark_in_progress",
    "mcp__features__feature_mark_passing",
    "mcp__features__feature_skip",
    "mcp__features__feature_create_bulk",
]

# Playwright MCP tools for browser automation
PLAYWRIGHT_TOOLS = [
    # Core navigation & screenshots
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_navigate_back",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_snapshot",

    # Element interaction
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_fill_form",
    "mcp__playwright__browser_select_option",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_drag",
    "mcp__playwright__browser_press_key",

    # JavaScript & debugging
    "mcp__playwright__browser_evaluate",
    # "mcp__playwright__browser_run_code",  # REMOVED - causes Playwright MCP server crash
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",

    # Browser management
    "mcp__playwright__browser_close",
    "mcp__playwright__browser_resize",
    "mcp__playwright__browser_tabs",
    "mcp__playwright__browser_wait_for",
    "mcp__playwright__browser_handle_dialog",
    "mcp__playwright__browser_file_upload",
    "mcp__playwright__browser_install",
]

# Built-in tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "WebFetch",
    "WebSearch",
]


# ============================================================================
# Enhanced Hooks (SDK 0.1.19 / Claude Code v2.1.1)
# ============================================================================

def post_tool_use_hook(tool_name: str, tool_input: dict, tool_result: str) -> None:
    """
    PostToolUse hook for logging tool executions.

    This provides an audit trail of all tool calls and their results,
    useful for debugging and monitoring agent behavior.

    Args:
        tool_name: Name of the tool that was executed
        tool_input: Input parameters passed to the tool
        tool_result: Result returned by the tool
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Truncate large results for logging
    result_preview = str(tool_result)[:200]
    if len(str(tool_result)) > 200:
        result_preview += "..."

    logger.debug(
        f"[{timestamp}] Tool executed: {tool_name} | "
        f"Result length: {len(str(tool_result))} chars"
    )

    # Log more details at trace level if available
    if logger.isEnabledFor(logging.DEBUG):
        input_str = json.dumps(tool_input, default=str)[:300]
        logger.debug(f"  Input: {input_str}")
        logger.debug(f"  Result: {result_preview}")


def session_start_hook(session_id: str, **kwargs) -> None:
    """
    SessionStart hook called when agent session begins.

    Args:
        session_id: Unique identifier for this session
        **kwargs: Additional session metadata
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"[{timestamp}] Agent session started: {session_id}")


def session_end_hook(session_id: str, reason: str = "completed", **kwargs) -> None:
    """
    SessionEnd hook called when agent session ends.

    Args:
        session_id: Unique identifier for this session
        reason: Why the session ended (completed, error, max_turns, etc.)
        **kwargs: Additional session metadata
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"[{timestamp}] Agent session ended: {session_id} (reason: {reason})")


def create_client(project_dir: Path, model: str, yolo_mode: bool = False):
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        yolo_mode: If True, skip Playwright MCP server for rapid prototyping

    Returns:
        Configured ClaudeSDKClient (from claude_agent_sdk)

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
    2. Permissions - File operations restricted to project_dir only
    3. Security hooks - Bash commands validated against an allowlist
       (see security.py for ALLOWED_COMMANDS)

    Note: Authentication is handled by start.bat/start.sh before this runs.
    The Claude SDK auto-detects credentials from ~/.claude/.credentials.json
    """
    # Build allowed tools list based on mode
    # In YOLO mode, exclude Playwright tools for faster prototyping
    allowed_tools = [*BUILTIN_TOOLS, *FEATURE_MCP_TOOLS]
    if not yolo_mode:
        allowed_tools.extend(PLAYWRIGHT_TOOLS)

    # Build permissions list
    permissions_list = [
        # Allow all file operations within the project directory
        "Read(./**)",
        "Write(./**)",
        "Edit(./**)",
        "Glob(./**)",
        "Grep(./**)",
        # Bash permission granted here, but actual commands are validated
        # by the bash_security_hook (see security.py for allowed commands)
        "Bash(*)",
        # Allow web tools for documentation lookup
        "WebFetch",
        "WebSearch",
        # Allow Feature MCP tools for feature management
        *FEATURE_MCP_TOOLS,
    ]
    if not yolo_mode:
        # Allow Playwright MCP tools for browser automation (standard mode only)
        permissions_list.extend(PLAYWRIGHT_TOOLS)

    # Create comprehensive security settings
    # Note: Using relative paths ("./**") restricts access to project directory
    # since cwd is set to project_dir
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",  # Auto-approve edits within allowed directories
            "allow": permissions_list,
        },
    }

    # Ensure project directory exists before creating settings file
    project_dir.mkdir(parents=True, exist_ok=True)

    # Write settings to a file in the project directory
    settings_file = project_dir / ".claude_settings.json"
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    print(f"Created security settings at {settings_file}")
    print("   - Sandbox enabled (OS-level bash isolation)")
    print(f"   - Filesystem restricted to: {project_dir.resolve()}")
    print("   - Bash commands restricted to allowlist (see security.py)")
    if yolo_mode:
        print("   - MCP servers: features (database) - YOLO MODE (no Playwright)")
    else:
        print("   - MCP servers: playwright (browser), features (database)")
    print("   - Project settings enabled (skills, commands, CLAUDE.md)")
    print()

    # Use system Claude CLI instead of bundled one (avoids Bun runtime crash on Windows)
    system_cli = shutil.which("claude")
    if system_cli:
        print(f"   - Using system CLI: {system_cli}")
    else:
        print("   - Warning: System Claude CLI not found, using bundled CLI")

    # Build MCP servers config - features is always included, playwright only in standard mode
    # Uses build_safe_mcp_env() to prevent credential leakage (only allowlisted vars)
    mcp_servers = {
        "features": {
            "command": sys.executable,  # Use the same Python that's running this script
            "args": ["-m", "mcp_server.feature_mcp"],
            "env": build_safe_mcp_env({
                "PROJECT_DIR": str(project_dir.resolve()),
                "PYTHONPATH": str(Path(__file__).parent.resolve()),
            }),
        },
    }
    if not yolo_mode:
        # Include Playwright MCP server for browser automation (standard mode only)
        mcp_servers["playwright"] = {
            "command": "npx",
            "args": ["@playwright/mcp@latest", "--viewport-size", "1280x720"],
        }

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            cli_path=system_cli,  # Use system CLI to avoid bundled Bun crash (exit code 3)
            system_prompt="You are an expert full-stack developer building a production-quality web application.",
            setting_sources=["project"],  # Enable skills, commands, and CLAUDE.md from project dir
            max_buffer_size=10 * 1024 * 1024,  # 10MB for large Playwright screenshots
            allowed_tools=allowed_tools,
            mcp_servers=mcp_servers,
            hooks={
                # Security: Validate bash commands against allowlist
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                ],
                # Audit: Log all tool executions (SDK 0.1.19)
                "PostToolUse": [
                    HookMatcher(matcher="*", hooks=[post_tool_use_hook]),
                ],
                # Lifecycle: Session start/end logging (SDK 0.1.19)
                "SessionStart": [session_start_hook],
                "SessionEnd": [session_end_hook],
            },
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),  # Use absolute path
        )
    )
