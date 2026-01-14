"""
Feature Analyzer Service
========================

Analyzes features using AI and expert skills to suggest improvements and extensions.
Uses Claude API with skills context to provide structured suggestions.
"""

import json
import logging
import os
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

logger = logging.getLogger(__name__)

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent


@dataclass
class Suggestion:
    """A single improvement suggestion for a feature."""
    id: str
    type: str  # ui_extension, validation, accessibility, performance, security
    title: str
    description: str
    priority: str  # high, medium, low
    skill_source: str
    implementation_steps: list[str] = field(default_factory=list)


@dataclass
class ComplexityAssessment:
    """Assessment of feature complexity."""
    score: int  # 1-10
    recommendation: str  # simple, split, complex


@dataclass
class AnalysisResult:
    """Result of feature analysis."""
    suggestions: list[Suggestion]
    complexity: ComplexityAssessment
    raw_response: str = ""


class FeatureAnalyzerSession:
    """
    Analyzes features through AI using expert skills.

    Uses multiple skills to provide comprehensive suggestions:
    - product-manager-toolkit: RICE prioritization, PRD templates
    - ux-researcher-designer: User stories, journey maps
    - senior-architect: Architecture impact assessment
    - senior-qa: Test coverage analysis
    - agile-product-owner: INVEST criteria, acceptance criteria
    """

    ANALYSIS_SKILLS = [
        "product-manager-toolkit",
        "ux-researcher-designer",
        "senior-architect",
        "senior-qa",
        "agile-product-owner",
    ]

    def __init__(self, project_name: str, project_dir: Path):
        """
        Initialize the analyzer session.

        Args:
            project_name: Name of the project
            project_dir: Path to the project directory
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.client: Optional[ClaudeSDKClient] = None
        self._client_entered: bool = False
        self.created_at = datetime.now()

    async def close(self) -> None:
        """Clean up resources and close the Claude client."""
        if self.client and self._client_entered:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing Claude client: {e}")
            finally:
                self._client_entered = False
                self.client = None

    def _load_skills_context(self) -> str:
        """Load skills context for feature analysis mode."""
        import sys
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))

        from lib.skills_loader import get_skills_context
        return get_skills_context(ROOT_DIR, "feature_analysis")

    def _load_prompt_template(self) -> str:
        """Load the feature analysis prompt template."""
        template_path = ROOT_DIR / ".claude" / "templates" / "feature_analysis_prompt.template.md"

        if template_path.exists():
            try:
                return template_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to load prompt template: {e}")

        # Fallback minimal template
        return """## Feature Analysis Request

You are analyzing a feature request using expert skills.

{{SKILLS_CONTEXT}}

### Feature to Analyze
- **Name**: {{FEATURE_NAME}}
- **Category**: {{FEATURE_CATEGORY}}
- **Description**: {{FEATURE_DESCRIPTION}}
- **Steps**: {{FEATURE_STEPS}}

Analyze this feature and suggest improvements.
Respond with a JSON object containing suggestions and complexity assessment.
"""

    def _build_analysis_prompt(
        self,
        name: str,
        category: str,
        description: str,
        steps: list[str]
    ) -> str:
        """Build the analysis prompt with feature details."""
        skills_context = self._load_skills_context()
        template = self._load_prompt_template()

        # Replace placeholders
        prompt = template.replace("{{SKILLS_CONTEXT}}", skills_context)
        prompt = prompt.replace("{{FEATURE_NAME}}", name)
        prompt = prompt.replace("{{FEATURE_CATEGORY}}", category)
        prompt = prompt.replace("{{FEATURE_DESCRIPTION}}", description)
        prompt = prompt.replace("{{FEATURE_STEPS}}", "\n".join(f"- {s}" for s in steps))

        return prompt

    async def _init_client(self) -> bool:
        """Initialize Claude client if not already initialized."""
        if self.client and self._client_entered:
            return True

        # Create security settings file
        security_settings = {
            "sandbox": {"enabled": False},
            "permissions": {
                "defaultMode": "acceptEdits",
                "allow": [],
            },
        }
        settings_file = self.project_dir / ".claude_analyzer_settings.json"
        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)

        # Use system CLI
        system_cli = shutil.which("claude")

        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model="claude-sonnet-4-20250514",  # Use Sonnet for faster analysis
                    cli_path=system_cli,
                    system_prompt="You are a feature analyzer that provides structured suggestions for improving features.",
                    allowed_tools=[],  # No tools needed for analysis
                    permission_mode="acceptEdits",
                    max_turns=2,
                    cwd=str(self.project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
            return True
        except Exception as e:
            logger.exception("Failed to create Claude client")
            return False

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Extract and parse JSON from response."""
        # Try to find JSON block in response
        import re

        # Look for ```json ... ``` blocks
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*"suggestions"[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Try the whole response as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        return None

    def _parse_suggestions(self, response: str) -> AnalysisResult:
        """Parse suggestions from Claude's response."""
        data = self._parse_json_response(response)

        suggestions = []
        complexity = ComplexityAssessment(score=5, recommendation="simple")

        if data:
            # Parse suggestions
            raw_suggestions = data.get("suggestions", [])
            for i, s in enumerate(raw_suggestions):
                suggestions.append(Suggestion(
                    id=f"suggestion-{i}",
                    type=s.get("type", "ui_extension"),
                    title=s.get("title", "Suggestion"),
                    description=s.get("description", ""),
                    priority=s.get("priority", "medium"),
                    skill_source=s.get("skill_source", "unknown"),
                    implementation_steps=s.get("implementation_steps", []),
                ))

            # Parse complexity
            raw_complexity = data.get("complexity_assessment", {})
            complexity = ComplexityAssessment(
                score=raw_complexity.get("score", 5),
                recommendation=raw_complexity.get("recommendation", "simple"),
            )

        return AnalysisResult(
            suggestions=suggestions,
            complexity=complexity,
            raw_response=response,
        )

    async def analyze_stream(
        self,
        name: str,
        category: str,
        description: str,
        steps: list[str]
    ) -> AsyncGenerator[dict, None]:
        """
        Analyze a feature and stream results.

        Args:
            name: Feature name
            category: Feature category
            description: Feature description
            steps: Test/implementation steps

        Yields:
            Message chunks with analysis progress and results
        """
        # Initialize client
        if not await self._init_client():
            yield {
                "type": "error",
                "content": "Failed to initialize Claude client"
            }
            return

        # Build prompt
        prompt = self._build_analysis_prompt(name, category, description, steps)

        yield {
            "type": "status",
            "content": "Analyzing feature with AI..."
        }

        try:
            # Send query to Claude
            await self.client.query(prompt)

            full_response = ""

            # Stream response
            async for msg in self.client.receive_response():
                msg_type = type(msg).__name__

                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__

                        if block_type == "TextBlock" and hasattr(block, "text"):
                            text = block.text
                            if text:
                                full_response += text
                                yield {
                                    "type": "text",
                                    "content": text
                                }

            # Parse final response
            result = self._parse_suggestions(full_response)

            # Yield parsed suggestions
            for suggestion in result.suggestions:
                yield {
                    "type": "suggestion",
                    "suggestion": {
                        "id": suggestion.id,
                        "type": suggestion.type,
                        "title": suggestion.title,
                        "description": suggestion.description,
                        "priority": suggestion.priority,
                        "skillSource": suggestion.skill_source,
                        "implementationSteps": suggestion.implementation_steps,
                    }
                }

            # Yield complexity assessment
            yield {
                "type": "complexity",
                "complexity": {
                    "score": result.complexity.score,
                    "recommendation": result.complexity.recommendation,
                }
            }

            yield {
                "type": "analysis_complete"
            }

        except Exception as e:
            logger.exception("Error during feature analysis")
            yield {
                "type": "error",
                "content": f"Analysis failed: {str(e)}"
            }


# Session registry with thread safety
_sessions: dict[str, FeatureAnalyzerSession] = {}
_sessions_lock = threading.Lock()


def get_analyzer_session(project_name: str) -> Optional[FeatureAnalyzerSession]:
    """Get an existing analyzer session for a project."""
    with _sessions_lock:
        return _sessions.get(project_name)


async def create_analyzer_session(project_name: str, project_dir: Path) -> FeatureAnalyzerSession:
    """Create a new analyzer session for a project."""
    old_session: Optional[FeatureAnalyzerSession] = None

    with _sessions_lock:
        old_session = _sessions.pop(project_name, None)
        session = FeatureAnalyzerSession(project_name, project_dir)
        _sessions[project_name] = session

    if old_session:
        try:
            await old_session.close()
        except Exception as e:
            logger.warning(f"Error closing old analyzer session: {e}")

    return session


async def remove_analyzer_session(project_name: str) -> None:
    """Remove and close an analyzer session."""
    session: Optional[FeatureAnalyzerSession] = None

    with _sessions_lock:
        session = _sessions.pop(project_name, None)

    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing analyzer session: {e}")


async def cleanup_analyzer_sessions() -> None:
    """Close all active analyzer sessions."""
    sessions_to_close: list[FeatureAnalyzerSession] = []

    with _sessions_lock:
        sessions_to_close = list(_sessions.values())
        _sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing analyzer session: {e}")
