"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.

Includes:
- Error classification for intelligent error handling
- Failure tracking with auto-pause on repeated failures
- User-friendly error messages
"""

import asyncio
import io
import logging
import sys
from pathlib import Path
from typing import Optional, Callable

from claude_agent_sdk import ClaudeSDKClient

# Fix Windows console encoding for Unicode characters (emoji, etc.)
# Without this, print() crashes when Claude outputs emoji like ✅
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from client import create_client
from progress import has_features, print_progress_summary, print_session_header
from prompts import (
    copy_spec_to_project,
    get_coding_prompt,
    get_coding_prompt_yolo,
    get_initializer_prompt,
    get_regression_prompt,
    load_prompt,
)
from lib import (
    classify_error,
    get_user_friendly_message,
    FailureTracker,
    FailureStats,
    ErrorInfo,
    ensure_browser_available,
)

logger = logging.getLogger(__name__)

# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3


async def run_agent_session(
    client: ClaudeSDKClient,
    message: str,
    project_dir: Path,
) -> tuple[str, str, Optional[ErrorInfo]]:
    """
    Run a single agent session using Claude Agent SDK.

    Args:
        client: Claude SDK client
        message: The prompt to send
        project_dir: Project directory path

    Returns:
        (status, response_text, error_info) where:
        - status: "continue" if agent should continue, "error" if an error occurred
        - response_text: The response text from the agent
        - error_info: Classified error info if an error occurred, None otherwise
    """
    print("Sending prompt to Claude Agent SDK...\n")

    try:
        # Send the query
        await client.query(message)

        # Collect response text and show tool use
        response_text = ""
        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            # Handle AssistantMessage (text and tool use)
            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        print(f"\n[Tool: {block.name}]", flush=True)
                        if hasattr(block, "input"):
                            input_str = str(block.input)
                            if len(input_str) > 200:
                                print(f"   Input: {input_str[:200]}...", flush=True)
                            else:
                                print(f"   Input: {input_str}", flush=True)

            # Handle UserMessage (tool results)
            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "ToolResultBlock":
                        result_content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)

                        # Check if command was blocked by security hook
                        if "blocked" in str(result_content).lower():
                            print(f"   [BLOCKED] {result_content}", flush=True)
                        elif is_error:
                            # Show errors (truncated)
                            error_str = str(result_content)[:500]
                            print(f"   [Error] {error_str}", flush=True)
                        else:
                            # Tool succeeded - just show brief confirmation
                            print("   [Done]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text, None

    except Exception as e:
        # Classify the error for intelligent handling
        error_info = classify_error(e)
        user_message = get_user_friendly_message(error_info)

        print(f"\nError during agent session: {user_message}")
        logger.error(f"Agent error: {error_info.type.value} - {error_info.message}")

        return "error", str(e), error_info


def _default_pause_callback(stats: FailureStats, error_info: ErrorInfo) -> None:
    """Default callback when failure tracker triggers a pause."""
    print("\n" + "=" * 70)
    print("  AUTO-PAUSE TRIGGERED")
    print("=" * 70)
    print(f"\nReason: {stats.pause_reason}")
    print(f"Failures in window: {stats.failures_in_window}")
    print(f"Total failures: {stats.total_failures}")
    if error_info.retry_after:
        print(f"Suggested wait time: {error_info.retry_after} seconds")
    print("\nTo resume, run the agent again.")
    print("=" * 70 + "\n")


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
    yolo_mode: bool = False,
    mode: Optional[str] = None,
    on_pause: Optional[Callable[[FailureStats, ErrorInfo], None]] = None,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        max_iterations: Maximum number of iterations (None for unlimited)
        yolo_mode: If True, skip browser testing and use YOLO prompt
        mode: Force specific mode ("initializer", "coding", "analysis", "regression", or None for auto-detect)
        on_pause: Optional callback when auto-pause is triggered due to failures
    """
    # Initialize failure tracker with callback
    failure_tracker = FailureTracker(
        on_pause_triggered=on_pause or _default_pause_callback
    )

    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT DEMO")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print(f"Model: {model}")

    # Determine mode
    if mode == "analysis":
        print("Mode: Analysis (scanning existing project)")
    elif mode == "regression":
        print("Mode: Regression (verification only)")
    elif yolo_mode:
        print("Mode: YOLO (testing disabled)")
    else:
        print("Mode: Standard (full testing)")

    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check browser availability for standard mode (not YOLO, not analysis)
    if not yolo_mode and mode != "analysis":
        print("\nChecking Playwright browser availability...")
        browser_ok, was_installed, browser_msg = ensure_browser_available(timeout=300)

        if not browser_ok:
            print(f"\nBrowser not available: {browser_msg}")
            print("Switching to YOLO mode (browser testing disabled)")
            yolo_mode = True
        elif was_installed:
            print(f"Browser was installed: {browser_msg}")
        else:
            print(f"Browser check: {browser_msg}")

    # Handle analysis mode
    if mode == "analysis":
        print("=" * 70)
        print("  ANALYSIS MODE")
        print("  Scanning project to identify features and improvements")
        print("=" * 70)
        print()
        is_first_run = False
        is_analysis_mode = True
        is_regression_mode = False
    elif mode == "regression":
        print("=" * 70)
        print("  REGRESSION MODE")
        print("  Verifying previously passing features")
        print("=" * 70)
        print()
        is_first_run = False
        is_analysis_mode = False
        is_regression_mode = True
        if max_iterations is None:
            max_iterations = 1
    else:
        is_analysis_mode = False
        is_regression_mode = False
        # Check if this is a fresh start or continuation
        # Uses has_features() which checks if the database actually has features,
        # not just if the file exists (empty db should still trigger initializer)
        if mode == "initializer":
            is_first_run = True
        elif mode == "coding":
            is_first_run = False
        else:
            is_first_run = not has_features(project_dir)

        if is_first_run:
            print("Fresh start - will use initializer agent")
            print()
            print("=" * 70)
            print("  NOTE: First session takes 10-20+ minutes!")
            print("  The agent is generating 200 detailed test cases.")
            print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
            print("=" * 70)
            print()
            # Copy the app spec into the project directory for the agent to read
            copy_spec_to_project(project_dir)
        else:
            print("Continuing existing project")
            print_progress_summary(project_dir)

    # Main loop
    iteration = 0

    while True:
        iteration += 1

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        # Print session header
        print_session_header(iteration, is_first_run)

        # Create client (fresh context)
        client = create_client(project_dir, model, yolo_mode=yolo_mode)

        # Choose prompt based on session type
        # Pass project_dir to enable project-specific prompts
        if is_analysis_mode:
            prompt = load_prompt("analysis_prompt", project_dir)
            # Analysis mode typically runs once - set max_iterations to 1 if not set
            if max_iterations is None:
                max_iterations = 1
        elif is_regression_mode:
            prompt = get_regression_prompt(project_dir)
        elif is_first_run:
            prompt = get_initializer_prompt(project_dir)
            is_first_run = False  # Only use initializer once
        else:
            # Use YOLO prompt if in YOLO mode
            if yolo_mode:
                prompt = get_coding_prompt_yolo(project_dir)
            else:
                prompt = get_coding_prompt(project_dir)

        # Run session with async context manager
        async with client:
            status, response, error_info = await run_agent_session(client, prompt, project_dir)

        # Handle status
        if status == "continue":
            # Record success to reset failure count
            failure_tracker.record_success()

            print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            # Track the failure and check if we should pause
            if error_info and failure_tracker.track_failure(error_info):
                # Failure tracker has triggered pause - exit the loop
                print("\nAgent paused due to repeated failures.")
                break

            # Not paused yet - retry with fresh session
            print("\nSession encountered an error")
            print("Will retry with a fresh session...")

            # Use retry_after if available, otherwise default delay
            delay = error_info.retry_after if error_info and error_info.retry_after else AUTO_CONTINUE_DELAY_SECONDS
            if error_info and error_info.is_rate_limit:
                print(f"Rate limit detected - waiting {delay} seconds before retry...")
            await asyncio.sleep(delay)

        # Small delay between sessions
        if max_iterations is None or iteration < max_iterations:
            print("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    if failure_tracker.is_paused:
        print("  SESSION PAUSED")
    else:
        print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print failure stats if any failures occurred
    stats = failure_tracker.get_stats()
    if stats.total_failures > 0:
        print(f"\nFailure stats: {stats.total_failures} total failures")
        if stats.paused_due_to_failures:
            print(f"  Paused: {stats.pause_reason}")

    # Print instructions for running the generated application
    if not failure_tracker.is_paused:
        print("\n" + "-" * 70)
        print("  TO RUN THE GENERATED APPLICATION:")
        print("-" * 70)
        print(f"\n  cd {project_dir.resolve()}")
        print("  ./init.sh           # Run the setup script")
        print("  # Or manually:")
        print("  npm install && npm run dev")
        print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
        print("-" * 70)

    print("\nDone!")
