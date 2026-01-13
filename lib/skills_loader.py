"""
Skills Loader
=============

Loads and manages skills from .claude/skills/ directory
for context injection into agent prompts.

This module provides:
- Parsing of SKILL.md files with YAML frontmatter
- Categorization of skills by agent mode (analysis, coding, frontend, etc.)
- Generation of skills context strings for prompt injection
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillInfo:
    """Parsed skill information from SKILL.md."""
    name: str
    description: str
    path: Path
    license: Optional[str] = None
    has_scripts: bool = False
    has_references: bool = False
    tags: list[str] = field(default_factory=list)


# Skills categorization for different agent modes
# Maps mode names to lists of relevant skill directory names
SKILL_CATEGORIES: dict[str, list[str]] = {
    # Analysis mode - for examining existing codebases
    "analysis": [
        "senior-architect",
        "code-reviewer",
        "senior-fullstack",
        "cto-advisor",
    ],
    # Coding mode - general development
    "coding": [
        "senior-fullstack",
        "senior-frontend",
        "senior-backend",
        "code-reviewer",
    ],
    # Architecture mode - system design
    "architecture": [
        "senior-architect",
        "senior-fullstack",
        "cto-advisor",
    ],
    # Architecture planning mode - designing implementation order
    "architecture_planning": [
        "senior-architect",
        "product-manager-toolkit",
        "senior-fullstack",
    ],
    # Frontend mode - UI development
    "frontend": [
        "senior-frontend",
        "frontend-design",
        "ui-design-system",
        "ux-researcher-designer",
    ],
    # Backend mode - API and server development
    "backend": [
        "senior-backend",
        "senior-data-engineer",
        "senior-architect",
    ],
    # Testing mode - QA and test automation
    "testing": [
        "senior-qa",
        "playwright-expert",
        "code-reviewer",
    ],
    # DevOps mode - infrastructure and deployment
    "devops": [
        "senior-devops",
        "senior-architect",
    ],
    # Product mode - product management
    "product": [
        "product-manager-toolkit",
        "product-strategist",
        "agile-product-owner",
        "scrum-master",
    ],
    # ML/AI mode - machine learning
    "ml": [
        "senior-ml-engineer",
        "senior-data-engineer",
        "senior-prompt-engineer",
    ],
    # Prompting mode - LLM optimization
    "prompting": [
        "senior-prompt-engineer",
        "senior-ml-engineer",
    ],
    # Initializer mode - project setup with architectural planning
    # Uses architect for structure and product-manager for prioritization
    "initializer": [
        "senior-architect",
        "product-manager-toolkit",
    ],
    # Spec analysis mode - for analyzing uploaded app-specs
    # Uses architect for structure, product-manager for requirements quality,
    # and CTO for tech stack evaluation
    "spec_analysis": [
        "senior-architect",
        "product-manager-toolkit",
        "cto-advisor",
        "code-reviewer",
    ],
}

# Maximum number of skills to include in context to avoid token bloat
MAX_SKILLS_IN_CONTEXT = 5


class SkillsLoader:
    """
    Load and manage skills from .claude/skills/ directory.

    Skills are discovered by scanning for SKILL.md files in subdirectories.
    Each skill can have optional scripts/ and references/ folders.

    Usage:
        loader = SkillsLoader(project_dir)
        skills = loader.load_all_skills()
        context = loader.generate_skills_context("coding")
    """

    def __init__(self, project_dir: Path):
        """
        Initialize the skills loader.

        Args:
            project_dir: Root directory of the project (or harness)
        """
        self.project_dir = project_dir
        self.skills_dir = project_dir / ".claude" / "skills"
        self.skills: dict[str, SkillInfo] = {}
        self._loaded = False

    def load_all_skills(self) -> dict[str, SkillInfo]:
        """
        Load all skills from .claude/skills/ directory.

        Returns:
            Dictionary mapping skill names to SkillInfo objects
        """
        if self._loaded:
            return self.skills

        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return {}

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    try:
                        skill_info = self._parse_skill(skill_dir, skill_md)
                        self.skills[skill_dir.name] = skill_info
                        logger.debug(f"Loaded skill: {skill_dir.name}")
                    except Exception as e:
                        logger.warning(f"Failed to parse skill {skill_dir.name}: {e}")
                        # Create minimal skill info as fallback
                        self.skills[skill_dir.name] = SkillInfo(
                            name=skill_dir.name,
                            description=f"Skill from {skill_dir.name}",
                            path=skill_dir,
                        )

        self._loaded = True
        logger.info(f"Loaded {len(self.skills)} skills from {self.skills_dir}")
        return self.skills

    def _parse_skill(self, skill_dir: Path, skill_md: Path) -> SkillInfo:
        """
        Parse SKILL.md frontmatter and content.

        Expects YAML frontmatter in format:
        ---
        name: skill-name
        description: Skill description
        license: MIT
        ---

        Args:
            skill_dir: Directory containing the skill
            skill_md: Path to SKILL.md file

        Returns:
            Parsed SkillInfo object
        """
        content = skill_md.read_text(encoding="utf-8")

        # Default values from directory name
        name = skill_dir.name
        description = ""
        license_info = None
        tags: list[str] = []

        # Parse YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                # Simple YAML parsing (avoiding external dependency)
                for line in frontmatter.strip().split("\n"):
                    line = line.strip()
                    if not line or ":" not in line:
                        continue

                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip().strip('"').strip("'")

                    if key == "name":
                        name = value
                    elif key == "description":
                        description = value
                    elif key == "license":
                        license_info = value
                    elif key == "tags":
                        # Handle comma-separated tags
                        tags = [t.strip() for t in value.split(",")]

        # If no description in frontmatter, try to extract from first paragraph
        if not description and "---" in content:
            body = content.split("---", 2)[-1].strip()
            # Take first non-empty line as description
            for line in body.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:200]  # Limit length
                    break

        return SkillInfo(
            name=name,
            description=description,
            path=skill_dir,
            license=license_info,
            has_scripts=(skill_dir / "scripts").exists(),
            has_references=(skill_dir / "references").exists(),
            tags=tags,
        )

    def get_skills_for_mode(self, mode: str) -> list[SkillInfo]:
        """
        Get relevant skills for a specific agent mode.

        Args:
            mode: Agent mode (analysis, coding, frontend, etc.)

        Returns:
            List of SkillInfo objects relevant to the mode
        """
        if not self._loaded:
            self.load_all_skills()

        category_skills = SKILL_CATEGORIES.get(mode, [])

        # Return skills in category order, limited to MAX_SKILLS_IN_CONTEXT
        result = []
        for skill_name in category_skills:
            if skill_name in self.skills and len(result) < MAX_SKILLS_IN_CONTEXT:
                result.append(self.skills[skill_name])

        return result

    def generate_skills_context(self, mode: str) -> str:
        """
        Generate skills context string for prompt injection.

        Args:
            mode: Agent mode (analysis, coding, frontend, etc.)

        Returns:
            Formatted string describing available skills
        """
        skills = self.get_skills_for_mode(mode)

        if not skills:
            return ""

        lines = [
            "The following expert skills are available to guide your work:\n"
        ]

        for skill in skills:
            # Format skill entry
            lines.append(f"- **{skill.name}**: {skill.description}")
            if skill.has_references:
                lines.append(f"  _(has reference documentation in .claude/skills/{skill.path.name}/references/)_")

        lines.append("")
        lines.append(
            "Consider these skills' guidelines and best practices when working on related tasks. "
            "For detailed guidance, reference the skill's documentation."
        )

        return "\n".join(lines)

    def get_skill(self, name: str) -> Optional[SkillInfo]:
        """
        Get a specific skill by name.

        Args:
            name: Skill directory name

        Returns:
            SkillInfo if found, None otherwise
        """
        if not self._loaded:
            self.load_all_skills()

        return self.skills.get(name)

    def list_all_modes(self) -> list[str]:
        """Get list of all available modes."""
        return list(SKILL_CATEGORIES.keys())

    def list_all_skills(self) -> list[str]:
        """Get list of all loaded skill names."""
        if not self._loaded:
            self.load_all_skills()

        return list(self.skills.keys())


# Convenience function for one-off usage
def get_skills_context(project_dir: Path, mode: str) -> str:
    """
    Convenience function to get skills context for a mode.

    Args:
        project_dir: Project directory path
        mode: Agent mode

    Returns:
        Skills context string
    """
    loader = SkillsLoader(project_dir)
    return loader.generate_skills_context(mode)
