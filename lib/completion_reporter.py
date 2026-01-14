"""
Completion Reporter
===================

Generates completion reports and documentation when a project reaches 100%
feature completion. This includes:

- COMPLETION_REPORT.md with full project summary
- Updated README.md with final status
- Feature export to markdown format
- Webhook notification for external integrations
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class CompletionStats:
    """Statistics for project completion."""

    total_features: int
    passing_features: int
    categories: dict[str, int]  # category -> count
    layers: dict[str, int]  # layer_name -> count
    completion_date: datetime
    git_commits: int
    lines_of_code: int


@dataclass
class CompletionResult:
    """Result of completion check and reporting."""

    is_complete: bool
    remaining: int
    report_path: Optional[Path]
    stats: Optional[CompletionStats]


class CompletionReporter:
    """
    Handles project completion detection and report generation.
    """

    REPORT_FILENAME = "COMPLETION_REPORT.md"

    def __init__(self, project_dir: Path):
        """
        Initialize the completion reporter.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = Path(project_dir)
        self.db_path = self.project_dir / "features.db"

    def check_completion(self) -> CompletionResult:
        """
        Check if all features are complete and generate report if so.

        Returns:
            CompletionResult with completion status and report path
        """
        from api.database import Feature, create_database

        if not self.db_path.exists():
            return CompletionResult(
                is_complete=False,
                remaining=-1,
                report_path=None,
                stats=None,
            )

        engine, session_maker = create_database(self.project_dir)
        session = session_maker()

        try:
            total = session.query(Feature).count()
            passing = session.query(Feature).filter(Feature.passes == True).count()

            if total == 0:
                return CompletionResult(
                    is_complete=False,
                    remaining=0,
                    report_path=None,
                    stats=None,
                )

            remaining = total - passing

            if remaining > 0:
                return CompletionResult(
                    is_complete=False,
                    remaining=remaining,
                    report_path=None,
                    stats=None,
                )

            # All features complete - generate stats
            features = session.query(Feature).all()

            categories: dict[str, int] = {}
            layers: dict[str, int] = {}

            for f in features:
                cat = f.category or "unknown"
                categories[cat] = categories.get(cat, 0) + 1

                layer = f.arch_layer if f.arch_layer is not None else 8
                layer_name = self._get_layer_name(layer)
                layers[layer_name] = layers.get(layer_name, 0) + 1

            stats = CompletionStats(
                total_features=total,
                passing_features=passing,
                categories=categories,
                layers=layers,
                completion_date=datetime.now(),
                git_commits=self._count_git_commits(),
                lines_of_code=self._count_lines_of_code(),
            )

            # Generate report
            report_path = self.generate_report(stats, features)

            return CompletionResult(
                is_complete=True,
                remaining=0,
                report_path=report_path,
                stats=stats,
            )

        finally:
            session.close()
            engine.dispose()

    def generate_report(self, stats: CompletionStats, features: list) -> Path:
        """
        Generate the completion report markdown file.

        Args:
            stats: Completion statistics
            features: List of Feature objects

        Returns:
            Path to the generated report
        """
        project_name = self.project_dir.name

        # Group features by category
        by_category: dict[str, list] = {}
        for f in features:
            cat = f.category or "unknown"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f)

        # Generate feature list
        feature_sections = []
        for category, cat_features in sorted(by_category.items()):
            section = f"### {category.replace('_', ' ').title()} ({len(cat_features)} features)\n\n"
            for f in cat_features:
                section += f"- **{f.name}**: {f.description[:100]}{'...' if len(f.description) > 100 else ''}\n"
            feature_sections.append(section)

        features_md = "\n".join(feature_sections)

        # Generate layers summary
        layers_md = "\n".join(
            f"- **{name}**: {count} features"
            for name, count in sorted(stats.layers.items(), key=lambda x: x[0])
        )

        report = f"""# Project Completion Report

## Summary

| Metric | Value |
|--------|-------|
| Project | {project_name} |
| Total Features | {stats.total_features} |
| Completion Date | {stats.completion_date.strftime('%Y-%m-%d %H:%M')} |
| Git Commits | {stats.git_commits} |
| Lines of Code | {stats.lines_of_code:,} |

## Completion Status

All **{stats.total_features}** features have been successfully implemented and verified.

## Features by Category

{features_md}

## Architecture Layers

{layers_md}

## Categories Distribution

| Category | Count |
|----------|-------|
{chr(10).join(f"| {cat} | {count} |" for cat, count in sorted(stats.categories.items()))}

---

*Generated by Auto-Agent-Harness on {stats.completion_date.strftime('%Y-%m-%d %H:%M:%S')}*
"""

        report_path = self.project_dir / self.REPORT_FILENAME
        report_path.write_text(report, encoding="utf-8")

        logger.info(f"Generated completion report: {report_path}")
        return report_path

    def export_features_to_markdown(self) -> str:
        """
        Export all features to a markdown format for documentation.

        Returns:
            Markdown string with all features
        """
        from api.database import Feature, create_database

        if not self.db_path.exists():
            return "No features database found."

        engine, session_maker = create_database(self.project_dir)
        session = session_maker()

        try:
            features = session.query(Feature).order_by(Feature.priority).all()

            if not features:
                return "No features found."

            lines = ["# Features List\n"]

            current_category = None
            for f in features:
                if f.category != current_category:
                    current_category = f.category
                    lines.append(f"\n## {current_category or 'Uncategorized'}\n")

                status = "[x]" if f.passes else "[ ]"
                lines.append(f"- {status} **{f.name}** (ID: {f.id})")
                lines.append(f"  - {f.description}")

                if f.steps:
                    lines.append("  - Steps:")
                    for i, step in enumerate(f.steps, 1):
                        lines.append(f"    {i}. {step}")

            return "\n".join(lines)

        finally:
            session.close()
            engine.dispose()

    def send_completion_webhook(self, stats: CompletionStats) -> bool:
        """
        Send completion notification to configured webhook.

        Args:
            stats: Completion statistics

        Returns:
            True if webhook sent successfully, False otherwise
        """
        webhook_url = os.environ.get("PROGRESS_N8N_WEBHOOK_URL")

        if not webhook_url:
            logger.debug("No webhook URL configured, skipping notification")
            return False

        payload = {
            "event": "project_completed",
            "project": self.project_dir.name,
            "total_features": stats.total_features,
            "completion_date": stats.completion_date.isoformat(),
            "git_commits": stats.git_commits,
            "lines_of_code": stats.lines_of_code,
            "categories": stats.categories,
            "layers": stats.layers,
        }

        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info(f"Sent completion webhook: {response.status_code}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send completion webhook: {e}")
            return False

    def _count_git_commits(self) -> int:
        """Count total git commits in the project."""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    def _count_lines_of_code(self) -> int:
        """Count lines of code in the project (excluding node_modules, .git, etc.)."""
        try:
            # Try using cloc if available
            result = subprocess.run(
                ["cloc", "--json", "--quiet", "."],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("SUM", {}).get("code", 0)
        except Exception:
            pass

        # Fallback: simple line count
        total = 0
        extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt"}
        skip_dirs = {"node_modules", ".git", "venv", "__pycache__", "dist", "build"}

        try:
            for root, dirs, files in os.walk(self.project_dir):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        try:
                            path = Path(root) / file
                            total += sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
                        except Exception:
                            pass
        except Exception:
            pass

        return total

    def _get_layer_name(self, layer: int) -> str:
        """Get human-readable name for architectural layer."""
        names = {
            0: "Skeleton",
            1: "Database",
            2: "Backend Core",
            3: "Auth",
            4: "Backend Features",
            5: "Frontend Core",
            6: "Frontend Features",
            7: "Integration",
            8: "Quality",
        }
        return names.get(layer, f"Layer {layer}")


# Module-level function for easy access
def check_project_completion(project_dir: Path) -> CompletionResult:
    """
    Check if a project is complete and generate report if so.

    Args:
        project_dir: Path to the project directory

    Returns:
        CompletionResult with status and optional report path
    """
    reporter = CompletionReporter(project_dir)
    return reporter.check_completion()
