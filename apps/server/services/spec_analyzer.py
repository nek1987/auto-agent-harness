"""
Spec Analyzer Service
=====================

Provides deep analysis of app_spec.txt files using Claude.

Features:
- Validates spec structure and completeness
- Analyzes quality and provides suggestions
- Can suggest refinements based on user feedback
- Caches analysis results per project
"""

import json
import logging
import os
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, List, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

# Import validation from prompts module (relative import for server context)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from prompts import SpecValidationResult, validate_spec_structure

logger = logging.getLogger(__name__)

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent.parent


@dataclass
class SpecAnalysisResult:
    """Result of deep analysis of an app_spec.txt file by Claude."""

    # Validation results
    validation: SpecValidationResult

    # Claude analysis
    strengths: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)

    # Suggested refinements
    suggested_changes: Optional[dict] = None
    refined_spec: Optional[str] = None

    # Metadata
    analysis_model: str = "claude-sonnet-4-20250514"
    analysis_timestamp: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "validation": self.validation.to_dict(),
            "strengths": self.strengths,
            "improvements": self.improvements,
            "critical_issues": self.critical_issues,
            "suggested_changes": self.suggested_changes,
            "refined_spec": self.refined_spec,
            "analysis_model": self.analysis_model,
            "analysis_timestamp": self.analysis_timestamp,
        }


# Prompt template for spec analysis
ANALYSIS_PROMPT_TEMPLATE = """You are analyzing an application specification (app_spec.txt) for quality and completeness.

## Spec Content
<spec>
{spec_content}
</spec>

## Analysis Requirements

Analyze this specification thoroughly and provide your assessment in the following JSON format:

```json
{{
  "strengths": [
    "List specific things that are well-defined in this spec"
  ],
  "improvements": [
    "List specific suggestions for improvement (not blocking)"
  ],
  "critical_issues": [
    "List any blocking problems that MUST be fixed before proceeding"
  ],
  "suggested_changes": {{
    "project_name": "suggested name if missing or unclear",
    "feature_count": "suggested count if unrealistic",
    "missing_sections": ["list of sections that should be added"]
  }}
}}
```

## Evaluation Criteria

1. **Completeness**: Does the spec have all required sections?
   - project_name, overview, technology_stack, feature_count, core_features

2. **Clarity**: Are descriptions clear and unambiguous?
   - Can a developer understand what to build?

3. **Technical Feasibility**: Is the spec realistic?
   - Feature count reasonable (typically 20-200)?
   - Technology choices appropriate?
   - Dependencies and complexity considered?

4. **Structure**: Is the XML format correct?
   - Proper nesting and closing tags?
   - Consistent formatting?

Output ONLY the JSON object, no additional text."""


REFINEMENT_PROMPT_TEMPLATE = """You are helping refine an application specification based on user feedback.

## Current Spec
<spec>
{spec_content}
</spec>

## User Feedback
{user_feedback}

## Task
Based on the feedback, generate an improved version of the spec.
Output the COMPLETE refined spec in valid XML format.
Preserve all existing content that doesn't need changing.
Make minimal changes that address the feedback.

Output ONLY the refined spec XML, no additional text or explanation."""


ENHANCE_PROMPT_TEMPLATE = """You are an expert at creating application specifications.

## User's Input
The user has provided the following text as a starting point for their app specification:

<input>
{spec_content}
</input>

## Task
Create a COMPLETE and VALID app_spec.txt based on this input.

Even if the input is minimal (just a description or idea), you should:
1. Extract the project concept and goals
2. Generate a full XML specification with ALL required sections
3. Make reasonable assumptions for missing details
4. Ensure the spec is immediately usable by a developer

## Required XML Structure
Your output MUST include these sections:
- <project_name> - derive from the input or create an appropriate name
- <overview> - describe the project based on user's input
- <technology_stack> - suggest appropriate technologies
- <feature_count> - estimate based on scope
- <core_features> - list main features derived from the concept

Optional but recommended sections:
- <database_schema>
- <api_endpoints>
- <implementation_steps>
- <success_criteria>

## Output Format
Output ONLY the complete XML spec, no additional text.
Start with <?xml version="1.0"?> and use <project_specification> as root element."""


class SpecAnalyzer:
    """
    Analyzes app_spec.txt files using Claude for quality and completeness.

    Usage:
        analyzer = SpecAnalyzer()
        result = await analyzer.analyze(spec_content)
        print(result.strengths)
        print(result.improvements)
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        temp_dir: Optional[Path] = None
    ):
        """
        Initialize the analyzer.

        Args:
            model: Claude model to use for analysis
            temp_dir: Temporary directory for Claude SDK (optional)
        """
        self.model = model
        self.temp_dir = temp_dir or Path.home() / ".auto-agent-harness" / "spec_analysis"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def analyze(self, spec_content: str) -> SpecAnalysisResult:
        """
        Analyze a spec using Claude.

        Args:
            spec_content: The content of the app_spec.txt file

        Returns:
            SpecAnalysisResult with validation and Claude analysis
        """
        # First, run local validation
        validation = validate_spec_structure(spec_content)

        # Initialize result
        result = SpecAnalysisResult(
            validation=validation,
            analysis_model=self.model,
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # If spec is completely invalid, skip Claude analysis
        if not validation.is_valid and validation.score < 20:
            result.critical_issues = validation.errors.copy()
            return result

        # Use Claude for deep analysis
        try:
            analysis_text = await self._query_claude(
                ANALYSIS_PROMPT_TEMPLATE.format(spec_content=spec_content)
            )

            # Parse the JSON response
            analysis_data = self._parse_analysis_json(analysis_text)

            if analysis_data:
                result.strengths = analysis_data.get("strengths", [])
                result.improvements = analysis_data.get("improvements", [])
                result.critical_issues = analysis_data.get("critical_issues", [])
                result.suggested_changes = analysis_data.get("suggested_changes")

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            # Fall back to validation-only results
            result.critical_issues = validation.errors.copy()
            result.improvements = validation.warnings.copy()

        return result

    async def suggest_refinements(
        self,
        spec_content: str,
        user_feedback: str
    ) -> str:
        """
        Generate a refined spec based on user feedback.

        Args:
            spec_content: The current spec content
            user_feedback: What the user wants to change

        Returns:
            Refined spec content
        """
        try:
            refined = await self._query_claude(
                REFINEMENT_PROMPT_TEMPLATE.format(
                    spec_content=spec_content,
                    user_feedback=user_feedback
                )
            )
            return refined.strip()
        except Exception as e:
            logger.error(f"Refinement failed: {e}")
            raise RuntimeError(f"Failed to generate refinements: {e}")

    async def enhance_spec(self, spec_content: str) -> dict:
        """
        Enhance an incomplete spec into a complete app_spec.txt.

        Takes any text input (even minimal descriptions) and generates
        a complete XML specification with all required sections.

        Args:
            spec_content: The incomplete or minimal spec content

        Returns:
            Dict with enhanced_spec, changes_made, and message
        """
        try:
            enhanced = await self._query_claude(
                ENHANCE_PROMPT_TEMPLATE.format(spec_content=spec_content)
            )
            enhanced = enhanced.strip()

            # Determine what changes were made
            changes_made = []
            validation_before = validate_spec_structure(spec_content)
            validation_after = validate_spec_structure(enhanced)

            if not validation_before.has_project_name and validation_after.has_project_name:
                changes_made.append("Added project name")
            if not validation_before.has_overview and validation_after.has_overview:
                changes_made.append("Added project overview")
            if not validation_before.has_tech_stack and validation_after.has_tech_stack:
                changes_made.append("Added technology stack")
            if not validation_before.has_feature_count and validation_after.has_feature_count:
                changes_made.append("Added feature count")
            if not validation_before.has_core_features and validation_after.has_core_features:
                changes_made.append("Added core features list")
            if not validation_before.has_database_schema and validation_after.has_database_schema:
                changes_made.append("Added database schema")
            if not validation_before.has_api_endpoints and validation_after.has_api_endpoints:
                changes_made.append("Added API endpoints")
            if not validation_before.has_implementation_steps and validation_after.has_implementation_steps:
                changes_made.append("Added implementation steps")
            if not validation_before.has_success_criteria and validation_after.has_success_criteria:
                changes_made.append("Added success criteria")

            if not changes_made:
                changes_made.append("Reformatted and validated XML structure")

            return {
                "enhanced_spec": enhanced,
                "changes_made": changes_made,
                "message": f"Spec enhanced successfully. Score improved from {validation_before.score} to {validation_after.score}.",
            }
        except Exception as e:
            logger.error(f"Enhancement failed: {e}")
            raise RuntimeError(f"Failed to enhance spec: {e}")

    async def analyze_streaming(
        self,
        spec_content: str
    ) -> AsyncGenerator[dict, None]:
        """
        Analyze a spec with streaming output.

        Yields progress updates and final result.

        Args:
            spec_content: The content of the app_spec.txt file

        Yields:
            Progress updates and final result
        """
        # Yield validation start
        yield {"type": "status", "message": "Running validation..."}

        # Run local validation
        validation = validate_spec_structure(spec_content)
        yield {
            "type": "validation",
            "result": validation.to_dict()
        }

        if not validation.is_valid and validation.score < 20:
            yield {
                "type": "error",
                "message": "Spec is too incomplete for Claude analysis"
            }
            return

        # Yield Claude analysis start
        yield {"type": "status", "message": "Analyzing with Claude..."}

        try:
            async for chunk in self._stream_claude_analysis(spec_content):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming analysis failed: {e}")
            yield {
                "type": "error",
                "message": f"Analysis failed: {str(e)}"
            }

    async def _query_claude(self, prompt: str) -> str:
        """
        Query Claude and return the complete response.

        Args:
            prompt: The prompt to send

        Returns:
            Claude's response text
        """
        # Create a temporary working directory for Claude SDK
        work_dir = self.temp_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal security settings
        settings = {
            "sandbox": {"enabled": False},
            "permissions": {"defaultMode": "acceptEdits", "allow": []},
        }
        settings_file = work_dir / ".claude_settings.json"
        with open(settings_file, "w") as f:
            json.dump(settings, f)

        # Use system CLI
        system_cli = shutil.which("claude")

        client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=self.model,
                cli_path=system_cli,
                system_prompt="You are a technical analyst reviewing application specifications.",
                allowed_tools=[],  # No tools needed for analysis
                max_turns=1,
                cwd=str(work_dir.resolve()),
                settings=str(settings_file.resolve()),
            )
        )

        response_text = ""
        try:
            async with client:
                await client.query(prompt)
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                                response_text += block.text
        finally:
            # Clean up temp directory
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass

        return response_text

    async def _stream_claude_analysis(
        self,
        spec_content: str
    ) -> AsyncGenerator[dict, None]:
        """
        Stream Claude analysis with progress updates.

        Args:
            spec_content: The spec content to analyze

        Yields:
            Analysis progress and results
        """
        # Create a temporary working directory
        work_dir = self.temp_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal security settings
        settings = {
            "sandbox": {"enabled": False},
            "permissions": {"defaultMode": "acceptEdits", "allow": []},
        }
        settings_file = work_dir / ".claude_settings.json"
        with open(settings_file, "w") as f:
            json.dump(settings, f)

        system_cli = shutil.which("claude")

        client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=self.model,
                cli_path=system_cli,
                system_prompt="You are a technical analyst reviewing application specifications.",
                allowed_tools=[],
                max_turns=1,
                cwd=str(work_dir.resolve()),
                settings=str(settings_file.resolve()),
            )
        )

        prompt = ANALYSIS_PROMPT_TEMPLATE.format(spec_content=spec_content)
        response_text = ""

        try:
            async with client:
                await client.query(prompt)
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                                chunk = block.text
                                response_text += chunk
                                yield {"type": "text", "content": chunk}

            # Parse and yield final result
            analysis_data = self._parse_analysis_json(response_text)
            if analysis_data:
                yield {
                    "type": "analysis_complete",
                    "result": analysis_data
                }
            else:
                yield {
                    "type": "error",
                    "message": "Failed to parse analysis result"
                }
        finally:
            # Clean up
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass

    def _parse_analysis_json(self, text: str) -> Optional[dict]:
        """
        Parse JSON from Claude's response.

        Handles cases where the JSON is wrapped in markdown code blocks.

        Args:
            text: Claude's response text

        Returns:
            Parsed dict or None if parsing fails
        """
        # Try to extract JSON from code blocks
        import re
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = text

        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.warning("Failed to parse analysis JSON")
            return None


# Cached analysis results per project
_analysis_cache: dict[str, SpecAnalysisResult] = {}
_cache_lock = threading.Lock()


def get_cached_analysis(project_name: str) -> Optional[SpecAnalysisResult]:
    """Get cached analysis result for a project."""
    with _cache_lock:
        return _analysis_cache.get(project_name)


def cache_analysis(project_name: str, result: SpecAnalysisResult) -> None:
    """Cache analysis result for a project."""
    with _cache_lock:
        _analysis_cache[project_name] = result


def clear_analysis_cache(project_name: Optional[str] = None) -> None:
    """Clear analysis cache for a project or all projects."""
    with _cache_lock:
        if project_name:
            _analysis_cache.pop(project_name, None)
        else:
            _analysis_cache.clear()
