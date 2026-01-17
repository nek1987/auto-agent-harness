"""
Feature Decomposer Service
==========================

Decomposes features into subtasks using selected skills.
Generates main tasks and extension tasks with implementation steps.
"""

import asyncio
import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

# Timeout and limits
AI_DECOMPOSITION_TIMEOUT = 180  # 3 minutes for decomposition
MAX_TURNS = 5  # Increased from 2 for complex decomposition

from .skills_catalog import SkillMetadata

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent.parent.parent


@dataclass
class SubTask:
    """A subtask generated from feature decomposition."""
    id: str
    title: str
    description: str
    type: str  # implementation, testing, documentation
    estimated_complexity: int  # 1-10
    assigned_skills: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # task IDs
    steps: list[str] = field(default_factory=list)
    is_extension: bool = False  # Extension/enhancement task

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "estimatedComplexity": self.estimated_complexity,
            "assignedSkills": self.assigned_skills,
            "dependencies": self.dependencies,
            "steps": self.steps,
            "isExtension": self.is_extension,
        }


@dataclass
class DecompositionResult:
    """Result of feature decomposition."""
    main_tasks: list[SubTask]
    extension_tasks: list[SubTask]
    total_complexity: int
    estimated_time: str
    skill_coverage: dict[str, list[str]]  # skill -> task titles

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "mainTasks": [t.to_dict() for t in self.main_tasks],
            "extensionTasks": [t.to_dict() for t in self.extension_tasks],
            "totalComplexity": self.total_complexity,
            "estimatedTime": self.estimated_time,
            "skillCoverage": self.skill_coverage,
        }


class FeatureDecomposer:
    """
    Decomposes features into implementable subtasks.

    Uses AI with selected skills context to generate:
    - Main implementation tasks
    - Testing tasks
    - Extension/enhancement tasks
    """

    def __init__(self, selected_skills: list[SkillMetadata]):
        """
        Initialize the decomposer with selected skills.

        Args:
            selected_skills: List of skills to use for decomposition
        """
        self.selected_skills = selected_skills
        self.client: Optional[ClaudeSDKClient] = None
        self._client_entered: bool = False

    async def close(self) -> None:
        """Clean up resources."""
        if self.client and self._client_entered:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing Claude client: {e}")
            finally:
                self._client_entered = False
                self.client = None

    def _load_skill_contexts(self) -> str:
        """Load relevant context from selected skills."""
        contexts = []

        for skill in self.selected_skills[:5]:  # Limit to top 5
            context = f"## {skill.display_name}\n"
            context += f"{skill.description}\n\n"

            if skill.capabilities:
                context += "**Capabilities:**\n"
                for cap in skill.capabilities[:5]:
                    context += f"- {cap}\n"

            contexts.append(context)

        return "\n\n".join(contexts)

    def _build_decomposition_prompt(
        self,
        name: str,
        category: str,
        description: str,
        steps: list[str],
    ) -> str:
        """Build the decomposition prompt."""
        skills_context = self._load_skill_contexts()
        skills_list = ", ".join(s.name for s in self.selected_skills)

        return f"""## Feature Decomposition Request

You are a senior technical lead decomposing a feature into implementable tasks.

### Selected Expert Skills
{skills_context}

### Feature to Decompose
- **Name**: {name}
- **Category**: {category}
- **Description**: {description}
- **Existing Steps**: {chr(10).join(f'- {s}' for s in steps) if steps else 'None provided'}

### Available Skills for Assignment
{skills_list}

### Task Types to Generate

1. **Main Implementation Tasks** (required)
   - Core functionality implementation
   - Database/API changes
   - UI components
   - Integration points

2. **Testing Tasks** (required)
   - Unit tests
   - Integration tests
   - E2E tests if applicable

3. **Extension Tasks** (optional enhancements)
   - Performance optimizations
   - Accessibility improvements
   - Analytics/monitoring
   - Error handling improvements

### Guidelines
- Each task should be completable in 1-4 hours
- Tasks should have clear acceptance criteria in steps
- Assign 1-3 skills per task
- Consider dependencies between tasks
- Extensions should add value but not block main feature

### Response Format
Respond with a JSON object:
```json
{{
  "main_tasks": [
    {{
      "title": "Task title",
      "description": "What this task accomplishes",
      "type": "implementation",
      "estimated_complexity": 5,
      "assigned_skills": ["senior-backend"],
      "dependencies": [],
      "steps": [
        "Step 1: Do something",
        "Step 2: Do something else"
      ]
    }}
  ],
  "extension_tasks": [
    {{
      "title": "Optional enhancement",
      "description": "What this improves",
      "type": "implementation",
      "estimated_complexity": 3,
      "assigned_skills": ["senior-frontend"],
      "dependencies": ["task-1"],
      "steps": ["..."]
    }}
  ],
  "explanation": "Brief explanation of decomposition strategy"
}}
```
"""

    async def _init_client(self, project_dir: Path) -> bool:
        """Initialize Claude client."""
        if self.client and self._client_entered:
            return True

        security_settings = {
            "sandbox": {"enabled": False},
            "permissions": {"defaultMode": "acceptEdits", "allow": []},
        }
        settings_file = project_dir / ".claude_decomposer_settings.json"
        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)

        system_cli = shutil.which("claude")

        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model="claude-sonnet-4-20250514",
                    cli_path=system_cli,
                    system_prompt="You are a technical lead expert at breaking down features into implementable tasks.",
                    allowed_tools=[],
                    permission_mode="acceptEdits",
                    max_turns=MAX_TURNS,
                    cwd=str(project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
            return True
        except Exception as e:
            logger.exception("Failed to create Claude client for decomposition")
            return False

    def _parse_decomposition_response(self, response: str) -> DecompositionResult:
        """Parse the AI response into structured result."""
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*"main_tasks"[\s\S]*\}', response)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    data = json.loads(response)

            main_tasks = []
            extension_tasks = []
            skill_coverage: dict[str, list[str]] = {}

            # Parse main tasks
            for i, task_data in enumerate(data.get("main_tasks", [])):
                task_id = f"task-{i + 1}"
                task = SubTask(
                    id=task_id,
                    title=task_data.get("title", f"Task {i + 1}"),
                    description=task_data.get("description", ""),
                    type=task_data.get("type", "implementation"),
                    estimated_complexity=task_data.get("estimated_complexity", 5),
                    assigned_skills=task_data.get("assigned_skills", []),
                    dependencies=task_data.get("dependencies", []),
                    steps=task_data.get("steps", []),
                    is_extension=False,
                )
                main_tasks.append(task)

                # Track skill coverage
                for skill in task.assigned_skills:
                    if skill not in skill_coverage:
                        skill_coverage[skill] = []
                    skill_coverage[skill].append(task.title)

            # Parse extension tasks
            for i, task_data in enumerate(data.get("extension_tasks", [])):
                task_id = f"ext-{i + 1}"
                task = SubTask(
                    id=task_id,
                    title=task_data.get("title", f"Extension {i + 1}"),
                    description=task_data.get("description", ""),
                    type=task_data.get("type", "implementation"),
                    estimated_complexity=task_data.get("estimated_complexity", 3),
                    assigned_skills=task_data.get("assigned_skills", []),
                    dependencies=task_data.get("dependencies", []),
                    steps=task_data.get("steps", []),
                    is_extension=True,
                )
                extension_tasks.append(task)

                for skill in task.assigned_skills:
                    if skill not in skill_coverage:
                        skill_coverage[skill] = []
                    skill_coverage[skill].append(task.title)

            # Calculate totals
            total_complexity = sum(t.estimated_complexity for t in main_tasks)
            total_complexity += sum(t.estimated_complexity for t in extension_tasks)

            # Estimate time (rough: complexity * 30 minutes)
            hours = (total_complexity * 30) / 60
            if hours < 1:
                estimated_time = f"~{int(hours * 60)} minutes"
            elif hours < 8:
                estimated_time = f"~{hours:.1f} hours"
            else:
                days = hours / 8
                estimated_time = f"~{days:.1f} days"

            return DecompositionResult(
                main_tasks=main_tasks,
                extension_tasks=extension_tasks,
                total_complexity=total_complexity,
                estimated_time=estimated_time,
                skill_coverage=skill_coverage,
            )

        except Exception as e:
            logger.exception("Failed to parse decomposition response")
            # Return minimal result
            return DecompositionResult(
                main_tasks=[SubTask(
                    id="task-1",
                    title="Implement feature",
                    description="Implement the feature as described",
                    type="implementation",
                    estimated_complexity=5,
                    assigned_skills=[s.name for s in self.selected_skills[:2]],
                    steps=["Implement the feature"],
                )],
                extension_tasks=[],
                total_complexity=5,
                estimated_time="~2.5 hours",
                skill_coverage={},
            )

    async def decompose_stream(
        self,
        name: str,
        category: str,
        description: str,
        steps: list[str],
        project_dir: Path,
    ) -> AsyncGenerator[dict, None]:
        """
        Decompose a feature into subtasks with streaming progress.

        Args:
            name: Feature name
            category: Feature category
            description: Feature description
            steps: Existing implementation steps
            project_dir: Path to project directory

        Yields:
            Progress messages and individual tasks
        """
        yield {
            "type": "status",
            "content": "Starting feature decomposition..."
        }

        # Initialize client
        if not await self._init_client(project_dir):
            yield {
                "type": "error",
                "content": "Failed to initialize AI client"
            }
            return

        # Build prompt
        prompt = self._build_decomposition_prompt(name, category, description, steps)

        yield {
            "type": "status",
            "content": f"Decomposing with {len(self.selected_skills)} selected skills..."
        }

        try:
            await self.client.query(prompt)

            full_response = ""
            timed_out = False

            # Stream response with timeout
            try:
                async with asyncio.timeout(AI_DECOMPOSITION_TIMEOUT):
                    async for msg in self.client.receive_response():
                        msg_type = type(msg).__name__
                        if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                            for block in msg.content:
                                if hasattr(block, "text"):
                                    full_response += block.text
                                    yield {
                                        "type": "text",
                                        "content": block.text
                                    }
            except asyncio.TimeoutError:
                timed_out = True
                logger.warning(f"Decomposition timed out after {AI_DECOMPOSITION_TIMEOUT}s")
                yield {
                    "type": "warning",
                    "content": f"Decomposition timed out after {AI_DECOMPOSITION_TIMEOUT}s. Using partial results."
                }

            yield {
                "type": "status",
                "content": "Parsing decomposition result..."
            }

            # Parse response (even if partial due to timeout)
            result = self._parse_decomposition_response(full_response)

            # Yield individual tasks
            for task in result.main_tasks:
                yield {
                    "type": "task_generated",
                    "task": task.to_dict()
                }

            for task in result.extension_tasks:
                yield {
                    "type": "task_generated",
                    "task": task.to_dict()
                }

            # Yield final result
            yield {
                "type": "decomposition_complete",
                "result": result.to_dict()
            }

        except Exception as e:
            logger.exception("Error during feature decomposition")
            yield {
                "type": "error",
                "content": f"Decomposition failed: {str(e)}"
            }


async def create_decomposer(
    selected_skills: list[SkillMetadata]
) -> FeatureDecomposer:
    """Create a new feature decomposer with selected skills."""
    return FeatureDecomposer(selected_skills)
