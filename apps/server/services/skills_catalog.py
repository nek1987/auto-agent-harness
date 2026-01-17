"""
Skills Catalog Service
======================

Indexes and provides search functionality for the skills catalog.
Parses SKILL.md files with YAML frontmatter and builds searchable index.
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """Metadata for a single skill."""
    name: str  # Directory name (e.g., "senior-backend")
    display_name: str  # Human-readable name from frontmatter
    description: str  # Full description for matching
    path: Path  # Path to skill directory
    tags: list[str] = field(default_factory=list)  # Extracted tags/categories
    capabilities: list[str] = field(default_factory=list)  # Extracted capabilities
    has_scripts: bool = False  # Has scripts/ directory
    has_references: bool = False  # Has references/ directory
    tech_stack: list[str] = field(default_factory=list)  # Extracted tech stack

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "displayName": self.display_name,
            "description": self.description,
            "tags": self.tags,
            "capabilities": self.capabilities,
            "hasScripts": self.has_scripts,
            "hasReferences": self.has_references,
            "techStack": self.tech_stack,
        }


@dataclass
class SkillsCatalogIndex:
    """Index of all skills in the catalog."""
    skills: dict[str, SkillMetadata] = field(default_factory=dict)  # name -> metadata
    by_tag: dict[str, list[str]] = field(default_factory=dict)  # tag -> skill names
    by_tech: dict[str, list[str]] = field(default_factory=dict)  # tech -> skill names


class SkillsCatalog:
    """
    Catalog service for indexing and searching skills.

    Scans the .claude/skills/ directory and builds a searchable index
    from SKILL.md files with YAML frontmatter.
    """

    # Category mappings for automatic tagging
    CATEGORY_KEYWORDS = {
        "frontend": ["react", "vue", "angular", "frontend", "ui", "css", "tailwind", "component"],
        "backend": ["backend", "api", "server", "express", "fastapi", "node", "database", "sql"],
        "fullstack": ["fullstack", "full-stack"],
        "devops": ["devops", "docker", "kubernetes", "ci/cd", "deployment", "infrastructure"],
        "testing": ["test", "qa", "quality", "e2e", "unit", "integration", "playwright"],
        "design": ["design", "ui", "ux", "figma", "accessibility", "color", "typography"],
        "architecture": ["architect", "architecture", "system design", "patterns", "diagram"],
        "data": ["data", "analytics", "ml", "machine learning", "etl", "pipeline"],
        "security": ["security", "auth", "authentication", "authorization", "encryption"],
        "documentation": ["doc", "documentation", "readme", "guide", "tutorial"],
        "product": ["product", "agile", "scrum", "backlog", "sprint", "user story"],
    }

    def __init__(self, skills_dir: Path):
        """
        Initialize the skills catalog.

        Args:
            skills_dir: Path to the .claude/skills/ directory
        """
        self.skills_dir = skills_dir
        self._index: Optional[SkillsCatalogIndex] = None
        self._lock = threading.Lock()

    def _parse_yaml_frontmatter(self, content: str) -> tuple[dict, str]:
        """
        Parse YAML frontmatter from markdown content.

        Args:
            content: Full file content

        Returns:
            Tuple of (frontmatter dict, remaining content)
        """
        if not content.startswith("---"):
            return {}, content

        # Find the closing ---
        end_match = re.search(r'\n---\s*\n', content[3:])
        if not end_match:
            return {}, content

        yaml_content = content[3:end_match.start() + 3]
        remaining = content[end_match.end() + 3:]

        try:
            frontmatter = yaml.safe_load(yaml_content) or {}
            return frontmatter, remaining
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML frontmatter: {e}")
            return {}, content

    def _extract_capabilities(self, content: str) -> list[str]:
        """Extract capabilities from skill content."""
        capabilities = []

        # Look for "## Core Capabilities" or similar sections
        cap_match = re.search(r'##\s*(?:Core\s+)?Capabilities(.*?)(?=\n##|\Z)', content, re.IGNORECASE | re.DOTALL)
        if cap_match:
            cap_section = cap_match.group(1)
            # Extract numbered items like "### 1. Api Scaffolder"
            items = re.findall(r'###\s*\d+\.\s*(.+)', cap_section)
            capabilities.extend(items)

        # Look for bullet points under "Features:" or "Main Capabilities"
        feature_matches = re.findall(r'[-*]\s+(.+?)(?:\n|$)', content)
        for match in feature_matches[:10]:  # Limit to first 10
            if len(match) < 100:  # Skip long lines
                capabilities.append(match.strip())

        return list(set(capabilities))[:15]  # Dedupe and limit

    def _extract_tech_stack(self, content: str) -> list[str]:
        """Extract tech stack from skill content."""
        tech_stack = []

        # Look for "## Tech Stack" section
        tech_match = re.search(r'##\s*Tech Stack(.*?)(?=\n##|\Z)', content, re.IGNORECASE | re.DOTALL)
        if tech_match:
            tech_section = tech_match.group(1)
            # Extract items after colons like "**Languages:** TypeScript, JavaScript"
            for line in tech_section.split('\n'):
                if ':' in line:
                    items_str = line.split(':', 1)[1]
                    items = [item.strip() for item in items_str.split(',')]
                    tech_stack.extend([item for item in items if item and len(item) < 30])

        return tech_stack[:20]  # Limit

    def _extract_tags(self, name: str, description: str, content: str) -> list[str]:
        """Extract tags based on content analysis."""
        tags = []
        combined_text = f"{name} {description} {content}".lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined_text:
                    tags.append(category)
                    break

        return list(set(tags))

    def _parse_skill(self, skill_dir: Path) -> Optional[SkillMetadata]:
        """
        Parse a single skill directory.

        Args:
            skill_dir: Path to skill directory

        Returns:
            SkillMetadata or None if parsing fails
        """
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return None

        try:
            content = skill_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {skill_file}: {e}")
            return None

        frontmatter, body = self._parse_yaml_frontmatter(content)

        name = skill_dir.name
        display_name = frontmatter.get("name", name.replace("-", " ").title())
        description = frontmatter.get("description", "")

        # If no description in frontmatter, try to get first paragraph
        if not description:
            first_para_match = re.search(r'\n\n(.+?)\n\n', body)
            if first_para_match:
                description = first_para_match.group(1).strip()

        capabilities = self._extract_capabilities(body)
        tech_stack = self._extract_tech_stack(body)
        tags = self._extract_tags(name, description, body)

        return SkillMetadata(
            name=name,
            display_name=display_name,
            description=description,
            path=skill_dir,
            tags=tags,
            capabilities=capabilities,
            has_scripts=(skill_dir / "scripts").is_dir(),
            has_references=(skill_dir / "references").is_dir(),
            tech_stack=tech_stack,
        )

    def build_index(self, force: bool = False) -> SkillsCatalogIndex:
        """
        Build or rebuild the skills index.

        Args:
            force: Force rebuild even if index exists

        Returns:
            The built index
        """
        with self._lock:
            if self._index and not force:
                return self._index

            logger.info(f"Building skills index from {self.skills_dir}")

            index = SkillsCatalogIndex()

            if not self.skills_dir.exists():
                logger.warning(f"Skills directory does not exist: {self.skills_dir}")
                self._index = index
                return index

            for skill_dir in self.skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill = self._parse_skill(skill_dir)
                if skill:
                    # Add to main index
                    index.skills[skill.name] = skill

                    # Add to tag index
                    for tag in skill.tags:
                        if tag not in index.by_tag:
                            index.by_tag[tag] = []
                        index.by_tag[tag].append(skill.name)

                    # Add to tech index
                    for tech in skill.tech_stack:
                        tech_lower = tech.lower()
                        if tech_lower not in index.by_tech:
                            index.by_tech[tech_lower] = []
                        index.by_tech[tech_lower].append(skill.name)

            logger.info(f"Indexed {len(index.skills)} skills")
            self._index = index
            return index

    def get_index(self) -> SkillsCatalogIndex:
        """Get the current index, building if necessary."""
        if not self._index:
            return self.build_index()
        return self._index

    def get_skill(self, name: str) -> Optional[SkillMetadata]:
        """
        Get a skill by name.

        Args:
            name: Skill name (directory name)

        Returns:
            SkillMetadata or None if not found
        """
        index = self.get_index()
        return index.skills.get(name)

    def get_all_skills(self) -> list[SkillMetadata]:
        """Get all skills in the catalog."""
        index = self.get_index()
        return list(index.skills.values())

    def search_by_tags(self, tags: list[str]) -> list[SkillMetadata]:
        """
        Search skills by tags.

        Args:
            tags: List of tags to search for

        Returns:
            List of matching skills (union of all tags)
        """
        index = self.get_index()
        matching_names = set()

        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in index.by_tag:
                matching_names.update(index.by_tag[tag_lower])

        return [index.skills[name] for name in matching_names if name in index.skills]

    def search_by_tech(self, techs: list[str]) -> list[SkillMetadata]:
        """
        Search skills by tech stack.

        Args:
            techs: List of technologies to search for

        Returns:
            List of matching skills
        """
        index = self.get_index()
        matching_names = set()

        for tech in techs:
            tech_lower = tech.lower()
            if tech_lower in index.by_tech:
                matching_names.update(index.by_tech[tech_lower])

        return [index.skills[name] for name in matching_names if name in index.skills]

    def search_by_keywords(self, keywords: list[str], limit: int = 20) -> list[SkillMetadata]:
        """
        Full-text search skills by keywords.

        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results

        Returns:
            List of matching skills, sorted by relevance
        """
        index = self.get_index()
        results = []

        keywords_lower = [k.lower() for k in keywords]

        for skill in index.skills.values():
            # Build searchable text
            searchable = f"{skill.name} {skill.display_name} {skill.description}".lower()
            searchable += " ".join(skill.tags).lower()
            searchable += " ".join(skill.tech_stack).lower()
            searchable += " ".join(skill.capabilities).lower()

            # Count keyword matches
            score = 0
            for keyword in keywords_lower:
                if keyword in searchable:
                    # Bonus for name match
                    if keyword in skill.name.lower():
                        score += 3
                    # Bonus for description match
                    elif keyword in skill.description.lower():
                        score += 2
                    else:
                        score += 1

            if score > 0:
                results.append((skill, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        return [skill for skill, _ in results[:limit]]

    def get_skills_by_category(self, category: str) -> list[SkillMetadata]:
        """
        Get all skills in a category.

        Args:
            category: Category name (e.g., "frontend", "backend")

        Returns:
            List of skills in that category
        """
        return self.search_by_tags([category])

    def get_catalog_summary(self) -> dict:
        """
        Get a summary of the catalog for display.

        Returns:
            Dictionary with catalog statistics
        """
        index = self.get_index()

        return {
            "totalSkills": len(index.skills),
            "categories": list(index.by_tag.keys()),
            "categoryCounts": {tag: len(names) for tag, names in index.by_tag.items()},
            "technologies": list(index.by_tech.keys())[:50],  # Limit for display
        }


# Global catalog instance
_catalog: Optional[SkillsCatalog] = None
_catalog_lock = threading.Lock()


def get_skills_catalog(skills_dir: Optional[Path] = None) -> SkillsCatalog:
    """
    Get the global skills catalog instance.

    Args:
        skills_dir: Optional path to skills directory (only used on first call)

    Returns:
        The skills catalog instance
    """
    global _catalog

    with _catalog_lock:
        if _catalog is None:
            if skills_dir is None:
                # Default to project root .claude/skills
                skills_dir = Path(__file__).parent.parent.parent.parent / ".claude" / "skills"
            _catalog = SkillsCatalog(skills_dir)

        return _catalog


def reset_skills_catalog() -> None:
    """Reset the global catalog (useful for testing)."""
    global _catalog

    with _catalog_lock:
        _catalog = None
