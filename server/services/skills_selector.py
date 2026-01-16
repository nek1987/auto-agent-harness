"""
Skills Selector Service
=======================

Selects the most relevant skills for a feature based on analysis.
Uses keyword matching, category mapping, and AI-assisted ranking.
"""

import asyncio
import json
import logging
import re
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

# Timeout and limits
AI_SELECTION_TIMEOUT = 120  # 2 minutes for AI skill selection
MAX_TURNS = 5  # Increased from 2 for complex analysis

from .skills_catalog import SkillMetadata, SkillsCatalog, get_skills_catalog

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent.parent


@dataclass
class SkillMatch:
    """A skill match with relevance scoring."""
    skill: SkillMetadata
    relevance_score: float  # 0.0 - 1.0
    match_reasons: list[str] = field(default_factory=list)
    category: str = "general"  # frontend, backend, testing, etc.

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.skill.name,
            "displayName": self.skill.display_name,
            "description": self.skill.description,
            "relevanceScore": self.relevance_score,
            "matchReasons": self.match_reasons,
            "category": self.category,
            "tags": self.skill.tags,
            "capabilities": self.skill.capabilities,
            "hasScripts": self.skill.has_scripts,
            "hasReferences": self.skill.has_references,
        }


@dataclass
class SkillsSelectionResult:
    """Result of skills selection."""
    primary_skills: list[SkillMatch]  # Top 5 most relevant
    secondary_skills: list[SkillMatch]  # Additional relevant skills
    all_matches: list[SkillMatch]  # All matches for user selection

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "primarySkills": [s.to_dict() for s in self.primary_skills],
            "secondarySkills": [s.to_dict() for s in self.secondary_skills],
            "allMatches": [s.to_dict() for s in self.all_matches],
        }


class SkillsSelector:
    """
    Selects relevant skills for a feature.

    Uses multiple strategies:
    1. Keyword matching against skill descriptions
    2. Category mapping based on feature category
    3. Tech stack detection
    4. Optional AI-assisted ranking for complex cases
    """

    # Category to skill mappings
    CATEGORY_SKILL_MAP = {
        "frontend": ["senior-frontend", "ui-design-system", "react-19-patterns", "tailwind-css"],
        "backend": ["senior-backend", "api-designer", "database-schema-designer"],
        "api": ["senior-backend", "api-designer", "api-test-generator"],
        "database": ["senior-backend", "database-schema-designer", "senior-data-engineer"],
        "authentication": ["senior-backend", "senior-architect", "api-designer"],
        "security": ["senior-backend", "senior-architect", "code-reviewer"],
        "ui": ["senior-frontend", "ui-design-system", "ux-researcher-designer"],
        "testing": ["senior-qa", "agent-browser", "web-design-guidelines", "test-suite-generator"],
        "devops": ["senior-devops", "dockerfile-generator", "docker-optimizer"],
        "architecture": ["senior-architect", "architecture-diagram-creator", "cto-advisor"],
        "documentation": ["technical-doc-creator", "readme-generator", "api-reference-creator"],
        "performance": ["senior-backend", "bottleneck-identifier", "api-load-tester"],
        "bug": ["senior-qa", "systematic-debugging", "code-reviewer"],
    }

    # Keywords that indicate specific skills
    KEYWORD_SKILL_MAP = {
        "react": ["senior-frontend", "react-19-patterns"],
        "next.js": ["senior-frontend", "senior-fullstack"],
        "node": ["senior-backend", "senior-fullstack"],
        "express": ["senior-backend", "api-designer"],
        "python": ["senior-backend", "senior-data-engineer"],
        "fastapi": ["senior-backend", "api-designer"],
        "graphql": ["senior-backend", "api-designer"],
        "rest": ["senior-backend", "api-designer"],
        "postgres": ["senior-backend", "database-schema-designer"],
        "sql": ["senior-backend", "senior-data-engineer"],
        "docker": ["senior-devops", "dockerfile-generator"],
        "kubernetes": ["senior-devops"],
        "oauth": ["senior-backend", "senior-architect"],
        "jwt": ["senior-backend", "api-designer"],
        "websocket": ["senior-backend", "senior-fullstack"],
        "form": ["senior-frontend", "ui-design-system"],
        "modal": ["senior-frontend", "ui-design-system"],
        "table": ["senior-frontend", "dashboard-creator"],
        "chart": ["senior-frontend", "dashboard-creator", "data-visualization"],
        "dashboard": ["senior-frontend", "dashboard-creator"],
        "login": ["senior-frontend", "senior-backend", "senior-architect"],
        "user": ["senior-backend", "senior-frontend", "agile-product-owner"],
        "admin": ["senior-fullstack", "senior-backend"],
        "payment": ["senior-backend", "senior-architect"],
        "email": ["senior-backend", "api-designer"],
        "notification": ["senior-backend", "senior-frontend"],
        "search": ["senior-backend", "senior-frontend"],
        "filter": ["senior-frontend", "senior-backend"],
        "upload": ["senior-backend", "senior-frontend"],
        "image": ["senior-backend", "senior-frontend"],
        "file": ["senior-backend", "file-operations"],
    }

    def __init__(self, catalog: Optional[SkillsCatalog] = None):
        """
        Initialize the skills selector.

        Args:
            catalog: Optional skills catalog (uses global if not provided)
        """
        self.catalog = catalog or get_skills_catalog()

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text."""
        # Convert to lowercase and split
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9.]+\b', text.lower())

        # Filter out common words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare",
            "ought", "used", "to", "for", "with", "from", "by", "at", "in", "on",
            "of", "and", "or", "but", "if", "then", "else", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more", "most",
            "other", "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "also", "now", "here", "there",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "user", "users", "should", "feature", "implement", "create", "add",
            "update", "delete", "get", "set", "make", "use", "using",
        }

        return [w for w in words if w not in stop_words and len(w) > 2]

    def _score_skill(
        self,
        skill: SkillMetadata,
        name: str,
        description: str,
        category: str,
        keywords: list[str]
    ) -> tuple[float, list[str]]:
        """
        Score a skill's relevance to a feature.

        Returns:
            Tuple of (score, match_reasons)
        """
        score = 0.0
        reasons = []

        # Check category mapping
        category_lower = category.lower()
        if category_lower in self.CATEGORY_SKILL_MAP:
            if skill.name in self.CATEGORY_SKILL_MAP[category_lower]:
                score += 0.3
                reasons.append(f"Matches category '{category}'")

        # Check keyword mapping
        for keyword in keywords:
            if keyword in self.KEYWORD_SKILL_MAP:
                if skill.name in self.KEYWORD_SKILL_MAP[keyword]:
                    score += 0.2
                    if f"Keyword '{keyword}'" not in reasons:
                        reasons.append(f"Keyword '{keyword}'")

        # Check skill tags
        for tag in skill.tags:
            if tag.lower() in category_lower or category_lower in tag.lower():
                score += 0.15
                if f"Tag match '{tag}'" not in reasons:
                    reasons.append(f"Tag match '{tag}'")

            for keyword in keywords:
                if keyword in tag.lower():
                    score += 0.1
                    break

        # Check skill description
        desc_lower = skill.description.lower()
        for keyword in keywords:
            if keyword in desc_lower:
                score += 0.05

        # Check capabilities
        caps_text = " ".join(skill.capabilities).lower()
        for keyword in keywords:
            if keyword in caps_text:
                score += 0.05

        # Check tech stack match
        feature_text = f"{name} {description}".lower()
        for tech in skill.tech_stack:
            if tech.lower() in feature_text:
                score += 0.1
                reasons.append(f"Tech '{tech}'")

        # Normalize score to 0-1 range
        score = min(1.0, score)

        return score, reasons

    def select_skills_for_feature(
        self,
        name: str,
        description: str,
        category: str,
        steps: list[str],
        max_primary: int = 5,
        max_secondary: int = 10,
    ) -> SkillsSelectionResult:
        """
        Select relevant skills for a feature.

        Args:
            name: Feature name
            description: Feature description
            category: Feature category
            steps: Implementation/test steps
            max_primary: Maximum primary skills
            max_secondary: Maximum secondary skills

        Returns:
            SkillsSelectionResult with ranked skills
        """
        # Build searchable text
        full_text = f"{name} {description} {' '.join(steps)}"
        keywords = self._extract_keywords(full_text)

        logger.debug(f"Extracted keywords: {keywords}")

        # Score all skills
        all_matches: list[SkillMatch] = []

        for skill in self.catalog.get_all_skills():
            score, reasons = self._score_skill(
                skill, name, description, category, keywords
            )

            if score > 0.1:  # Minimum threshold
                # Determine category for this skill
                skill_category = "general"
                for tag in skill.tags:
                    if tag in ["frontend", "backend", "testing", "devops", "design", "architecture"]:
                        skill_category = tag
                        break

                all_matches.append(SkillMatch(
                    skill=skill,
                    relevance_score=score,
                    match_reasons=reasons if reasons else ["General relevance"],
                    category=skill_category,
                ))

        # Sort by score
        all_matches.sort(key=lambda m: m.relevance_score, reverse=True)

        # Split into primary and secondary
        primary = all_matches[:max_primary]
        secondary = all_matches[max_primary:max_primary + max_secondary]

        return SkillsSelectionResult(
            primary_skills=primary,
            secondary_skills=secondary,
            all_matches=all_matches,
        )

    async def select_skills_with_ai(
        self,
        name: str,
        description: str,
        category: str,
        steps: list[str],
        project_dir: Path,
    ) -> AsyncGenerator[dict, None]:
        """
        Select skills using AI for better ranking.

        This method uses Claude to analyze the feature and provide
        more accurate skill recommendations.

        Yields:
            Progress messages and final selection result
        """
        yield {
            "type": "status",
            "content": "Analyzing feature requirements..."
        }

        # First get keyword-based selection
        initial_selection = self.select_skills_for_feature(
            name, description, category, steps
        )

        yield {
            "type": "status",
            "content": f"Found {len(initial_selection.all_matches)} potentially relevant skills"
        }

        # If we have few matches, just return the keyword-based selection
        if len(initial_selection.all_matches) <= 10:
            yield {
                "type": "skills_suggested",
                "selection": initial_selection.to_dict()
            }
            return

        # For more complex cases, use AI to re-rank
        yield {
            "type": "status",
            "content": "Using AI to rank skills..."
        }

        # Build candidate skills summary for AI
        candidates_summary = []
        for match in initial_selection.all_matches[:30]:  # Limit to top 30
            candidates_summary.append({
                "name": match.skill.name,
                "description": match.skill.description[:200],
                "tags": match.skill.tags,
                "initialScore": match.relevance_score,
            })

        # Build AI prompt
        prompt = f"""## Skills Selection Request

You are selecting the most relevant expert skills for implementing a feature.

### Feature Details
- **Name**: {name}
- **Category**: {category}
- **Description**: {description}
- **Steps**: {chr(10).join(f'- {s}' for s in steps)}

### Candidate Skills
{json.dumps(candidates_summary, indent=2)}

### Task
Select the top 5 most relevant skills for implementing this feature.
Consider:
1. Direct relevance to the feature's domain
2. Technical stack requirements
3. Quality aspects (testing, security, accessibility)

Respond with a JSON object:
```json
{{
  "selected_skills": [
    {{
      "name": "skill-name",
      "relevance_score": 0.95,
      "reasons": ["Reason 1", "Reason 2"]
    }}
  ],
  "explanation": "Brief explanation of selection strategy"
}}
```
"""

        try:
            # Initialize Claude client for AI ranking
            security_settings = {
                "sandbox": {"enabled": False},
                "permissions": {"defaultMode": "acceptEdits", "allow": []},
            }
            settings_file = project_dir / ".claude_skills_settings.json"
            with open(settings_file, "w") as f:
                json.dump(security_settings, f, indent=2)

            system_cli = shutil.which("claude")

            client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model="claude-sonnet-4-20250514",
                    cli_path=system_cli,
                    system_prompt="You are a skills selection expert.",
                    allowed_tools=[],
                    permission_mode="acceptEdits",
                    max_turns=MAX_TURNS,
                    cwd=str(project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                )
            )

            async with client:
                await client.query(prompt)

                full_response = ""
                try:
                    async with asyncio.timeout(AI_SELECTION_TIMEOUT):
                        async for msg in client.receive_response():
                            msg_type = type(msg).__name__
                            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                                for block in msg.content:
                                    if hasattr(block, "text"):
                                        full_response += block.text
                except asyncio.TimeoutError:
                    logger.warning(f"AI selection timed out after {AI_SELECTION_TIMEOUT}s, using partial response")
                    yield {
                        "type": "warning",
                        "content": "AI analysis timed out. Using partial results."
                    }

                # Parse AI response (even if partial)
                ai_selection = self._parse_ai_selection(full_response, initial_selection)

                yield {
                    "type": "skills_suggested",
                    "selection": ai_selection.to_dict()
                }

        except asyncio.TimeoutError:
            logger.warning("AI selection completely timed out")
            yield {
                "type": "skills_suggested",
                "selection": initial_selection.to_dict()
            }

        except Exception as e:
            logger.warning(f"AI selection failed, using keyword-based: {e}")
            # Fall back to keyword-based selection
            yield {
                "type": "skills_suggested",
                "selection": initial_selection.to_dict()
            }

    def _parse_ai_selection(
        self,
        response: str,
        fallback: SkillsSelectionResult
    ) -> SkillsSelectionResult:
        """Parse AI selection response."""
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                data = json.loads(response)

            selected = data.get("selected_skills", [])

            # Build new selection with AI scores
            primary = []
            skill_map = {m.skill.name: m for m in fallback.all_matches}

            for s in selected[:5]:
                name = s.get("name")
                if name in skill_map:
                    match = skill_map[name]
                    match.relevance_score = s.get("relevance_score", match.relevance_score)
                    match.match_reasons = s.get("reasons", match.match_reasons)
                    primary.append(match)

            # Keep secondary from fallback
            primary_names = {m.skill.name for m in primary}
            secondary = [m for m in fallback.all_matches if m.skill.name not in primary_names][:10]

            return SkillsSelectionResult(
                primary_skills=primary,
                secondary_skills=secondary,
                all_matches=fallback.all_matches,
            )

        except Exception as e:
            logger.warning(f"Failed to parse AI selection: {e}")
            return fallback


# Session management
_selector: Optional[SkillsSelector] = None
_selector_lock = threading.Lock()


def get_skills_selector(catalog: Optional[SkillsCatalog] = None) -> SkillsSelector:
    """Get the global skills selector instance."""
    global _selector

    with _selector_lock:
        if _selector is None:
            _selector = SkillsSelector(catalog)
        return _selector
