#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with Claude.
This script implements the two-agent pattern (initializer + coding agent) and
incorporates all the strategies from the long-running agents guide.

Example Usage:
    # Using absolute path directly
    python autonomous_agent_demo.py --project-dir C:/Projects/my-app

    # Using registered project name (looked up from registry)
    python autonomous_agent_demo.py --project-dir my-app

    # Limit iterations for testing
    python autonomous_agent_demo.py --project-dir my-app --max-iterations 5

    # YOLO mode: rapid prototyping without browser testing
    python autonomous_agent_demo.py --project-dir my-app --yolo

    # Import existing spec with analysis
    python autonomous_agent_demo.py --project-dir my-app --import-spec /path/to/spec.txt --analyze

    # Import spec without analysis (auto-approve for CI/CD)
    python autonomous_agent_demo.py --project-dir my-app --import-spec /path/to/spec.txt --auto-approve
"""

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# IMPORTANT: Must be called BEFORE importing other modules that read env vars at load time
load_dotenv()

from agent import run_autonomous_agent
from registry import get_project_path
from prompts import (
    import_spec_file,
    validate_spec_structure,
    SpecValidationResult,
)

# Configuration
# DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MODEL = "claude-opus-4-5-20251101"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Long-running agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use absolute path directly
  python autonomous_agent_demo.py --project-dir C:/Projects/my-app

  # Use registered project name (looked up from registry)
  python autonomous_agent_demo.py --project-dir my-app

  # Use a specific model
  python autonomous_agent_demo.py --project-dir my-app --model claude-sonnet-4-5-20250929

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir my-app --max-iterations 5

  # YOLO mode: rapid prototyping without browser testing
  python autonomous_agent_demo.py --project-dir my-app --yolo

Authentication:
  Uses Claude CLI credentials from ~/.claude/.credentials.json
  Run 'claude login' to authenticate (handled by start.bat/start.sh)
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Project directory path (absolute) or registered project name",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="Enable YOLO mode: rapid prototyping without browser testing",
    )

    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["initializer", "coding", "analysis", "regression"],
        help="Force specific agent mode (default: auto-detect based on features.db)",
    )

    # Spec import options
    parser.add_argument(
        "--import-spec",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to existing app_spec.txt file to import",
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        default=False,
        help="Analyze imported spec with Claude before processing",
    )

    parser.add_argument(
        "--auto-approve",
        action="store_true",
        default=False,
        help="Skip approval prompt for spec import (for CI/CD pipelines)",
    )

    return parser.parse_args()


def print_validation_report(result: SpecValidationResult) -> None:
    """Print a formatted validation report."""
    print("\n" + "=" * 60)
    print("  SPEC VALIDATION REPORT")
    print("=" * 60)

    # Score with color-coded status
    if result.score >= 80:
        status = "EXCELLENT"
    elif result.score >= 60:
        status = "GOOD"
    elif result.score >= 40:
        status = "FAIR"
    else:
        status = "NEEDS WORK"

    print(f"\nQuality Score: {result.score}/100 ({status})")
    print(f"Valid: {'Yes' if result.is_valid else 'No'}")

    if result.project_name:
        print(f"Project Name: {result.project_name}")
    if result.feature_count:
        print(f"Feature Count: {result.feature_count}")

    # Sections checklist
    print("\n--- Required Sections ---")
    sections = [
        ("Project Name", result.has_project_name),
        ("Overview", result.has_overview),
        ("Tech Stack", result.has_tech_stack),
        ("Feature Count", result.has_feature_count),
        ("Core Features", result.has_core_features),
    ]
    for name, present in sections:
        icon = "[+]" if present else "[ ]"
        print(f"  {icon} {name}")

    print("\n--- Optional Sections ---")
    optional = [
        ("Database Schema", result.has_database_schema),
        ("API Endpoints", result.has_api_endpoints),
        ("Implementation Steps", result.has_implementation_steps),
        ("Success Criteria", result.has_success_criteria),
    ]
    for name, present in optional:
        icon = "[+]" if present else "[ ]"
        print(f"  {icon} {name}")

    # Errors and warnings
    if result.errors:
        print("\n--- Errors ---")
        for error in result.errors:
            print(f"  [!] {error}")

    if result.warnings:
        print("\n--- Warnings ---")
        for warning in result.warnings:
            print(f"  [?] {warning}")

    print("=" * 60)


def handle_spec_import(
    project_dir: Path,
    spec_path: Path,
    analyze: bool,
    auto_approve: bool,
) -> bool:
    """
    Handle spec import with optional analysis.

    Returns True if spec was imported successfully and agent should run.
    Returns False if import was cancelled or failed.
    """
    print("\n" + "=" * 60)
    print("  IMPORTING SPEC")
    print("=" * 60)
    print(f"\nSpec file: {spec_path}")
    print(f"Project: {project_dir}")

    # Check if spec file exists
    if not spec_path.exists():
        print(f"\nError: Spec file not found: {spec_path}")
        return False

    # Read and validate the spec
    try:
        spec_content = spec_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"\nError reading spec file: {e}")
        return False

    # Validate locally
    validation = validate_spec_structure(spec_content)
    print_validation_report(validation)

    # If analyze flag is set, do Claude analysis
    if analyze:
        print("\nAnalyzing with Claude...")
        try:
            from server.services.spec_analyzer import SpecAnalyzer

            async def do_analysis():
                analyzer = SpecAnalyzer()
                return await analyzer.analyze(spec_content)

            analysis = asyncio.run(do_analysis())

            print("\n--- Claude Analysis ---")
            if analysis.strengths:
                print("\nStrengths:")
                for s in analysis.strengths:
                    print(f"  [+] {s}")

            if analysis.improvements:
                print("\nSuggested Improvements:")
                for i in analysis.improvements:
                    print(f"  [?] {i}")

            if analysis.critical_issues:
                print("\nCritical Issues:")
                for c in analysis.critical_issues:
                    print(f"  [!] {c}")

            print("-" * 60)

        except Exception as e:
            print(f"\nWarning: Claude analysis failed: {e}")
            print("Continuing with local validation only...")

    # Check if spec is valid
    if not validation.is_valid:
        print("\nSpec validation failed. Please fix the errors and try again.")
        return False

    # Approval
    if not auto_approve:
        print("\nOptions:")
        print("  [1] Import and continue with agent")
        print("  [2] Cancel import")
        print()

        try:
            choice = input("Your choice (1/2): ").strip()
            if choice != "1":
                print("Import cancelled.")
                return False
        except (KeyboardInterrupt, EOFError):
            print("\nImport cancelled.")
            return False

    # Do the import
    try:
        dest_path, _ = import_spec_file(
            project_dir=project_dir,
            spec_path=spec_path,
            validate=False,  # Already validated above
            spec_name="main",
        )
        print(f"\nSpec imported to: {dest_path}")
        return True

    except Exception as e:
        print(f"\nError importing spec: {e}")
        return False


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Note: Authentication is handled by start.bat/start.sh before this script runs.
    # The Claude SDK auto-detects credentials from ~/.claude/.credentials.json

    # Resolve project directory:
    # 1. If absolute path, use as-is
    # 2. Otherwise, look up from registry by name
    project_dir_input = args.project_dir
    project_dir = Path(project_dir_input)

    if project_dir.is_absolute():
        # Absolute path provided - use directly
        if not project_dir.exists():
            # Create it if importing a spec
            if args.import_spec:
                project_dir.mkdir(parents=True, exist_ok=True)
                print(f"Created project directory: {project_dir}")
            else:
                print(f"Error: Project directory does not exist: {project_dir}")
                return
    else:
        # Treat as a project name - look up from registry
        registered_path = get_project_path(project_dir_input)
        if registered_path:
            project_dir = registered_path
        else:
            print(f"Error: Project '{project_dir_input}' not found in registry")
            print("Use an absolute path or register the project first.")
            return

    # Handle spec import if specified
    if args.import_spec:
        spec_path = Path(args.import_spec)
        if not spec_path.is_absolute():
            spec_path = Path.cwd() / spec_path

        success = handle_spec_import(
            project_dir=project_dir,
            spec_path=spec_path,
            analyze=args.analyze,
            auto_approve=args.auto_approve,
        )

        if not success:
            return

        # Force initializer mode after import
        if args.mode is None:
            args.mode = "initializer"

    try:
        # Run the agent (MCP server handles feature database)
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=args.model,
                max_iterations=args.max_iterations,
                yolo_mode=args.yolo,
                mode=args.mode,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
