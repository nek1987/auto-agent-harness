"""
Complexity Analyzer Service
===========================

Analyzes feature complexity to determine if automatic decomposition is needed.
Uses multiple heuristics including step count, description analysis, and keyword detection.
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ComplexityAnalysis:
    """Result of complexity analysis."""
    score: int  # 1-10
    level: str  # "simple", "medium", "complex"
    should_decompose: bool
    reasons: list[str] = field(default_factory=list)
    suggested_approach: str = "direct"  # "direct", "recommend_decompose", "require_decompose"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "score": self.score,
            "level": self.level,
            "shouldDecompose": self.should_decompose,
            "reasons": self.reasons,
            "suggestedApproach": self.suggested_approach,
        }


class ComplexityAnalyzer:
    """
    Analyzes feature complexity using multiple heuristics.

    Scoring system:
    - Step count: +4 for 10+ steps, +2 for 5+ steps
    - Description length: +2 for 100+ words, +1 for 50+ words
    - Complexity keywords: +2 for multiple matches
    - Technical category: +1 for complex categories
    - Complex step content: +2 for validation/integration steps

    Thresholds:
    - score >= 7: require_decompose (must use Skills Analysis)
    - score >= 5: recommend_decompose (suggest Skills Analysis)
    - score < 5: direct (create as single feature)
    """

    # Thresholds
    SIMPLE_THRESHOLD = 3
    MEDIUM_THRESHOLD = 5
    COMPLEX_THRESHOLD = 7

    # Step count thresholds
    STEP_THRESHOLD_RECOMMEND = 5
    STEP_THRESHOLD_REQUIRE = 10

    # Complexity indicators in description
    COMPLEXITY_KEYWORDS: dict[str, list[str]] = {
        "high_scope": ["complete", "full", "entire", "comprehensive", "all", "multiple", "whole"],
        "integration": ["integrate", "connect", "sync", "api", "database", "external", "third-party"],
        "multi_component": ["and", "with", "including", "also", "plus", "along with"],
        "complex_actions": ["migrate", "refactor", "redesign", "overhaul", "rebuild", "restructure"],
    }

    # Complex categories that typically need more careful handling
    COMPLEX_CATEGORIES = [
        "api", "database", "authentication", "security", "architecture",
        "integration", "migration", "infrastructure", "devops", "performance"
    ]

    # Keywords in steps that indicate complexity
    COMPLEX_STEP_KEYWORDS = [
        "test", "verify", "validate", "integrate", "deploy", "migrate",
        "configure", "authenticate", "authorize", "encrypt", "decrypt",
        "optimize", "refactor", "debug", "rollback"
    ]

    def analyze(
        self,
        name: str,
        description: str,
        steps: list[str],
        category: str,
    ) -> ComplexityAnalysis:
        """
        Analyze feature complexity.

        Args:
            name: Feature name
            description: Feature description
            steps: List of test/implementation steps
            category: Feature category

        Returns:
            ComplexityAnalysis with score, level, and recommendations
        """
        score = 0
        reasons: list[str] = []

        # 1. Step count analysis (major factor)
        step_count = len(steps)
        if step_count >= self.STEP_THRESHOLD_REQUIRE:
            score += 4
            reasons.append(f"High step count ({step_count} steps)")
        elif step_count >= self.STEP_THRESHOLD_RECOMMEND:
            score += 2
            reasons.append(f"Moderate step count ({step_count} steps)")

        # 2. Description length analysis
        desc_words = len(description.split())
        if desc_words > 100:
            score += 2
            reasons.append(f"Long description ({desc_words} words)")
        elif desc_words > 50:
            score += 1
            reasons.append(f"Moderate description length ({desc_words} words)")

        # 3. Keyword analysis
        desc_lower = description.lower()
        name_lower = name.lower()
        full_text = f"{name_lower} {desc_lower}"

        for indicator, keywords in self.COMPLEXITY_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in full_text]
            if len(matches) >= 2:
                score += 2
                indicator_name = indicator.replace("_", " ").title()
                reasons.append(f"{indicator_name} indicators: {', '.join(matches[:3])}")
            elif len(matches) >= 1 and indicator in ["complex_actions", "integration"]:
                score += 1
                indicator_name = indicator.replace("_", " ").title()
                reasons.append(f"{indicator_name}: {matches[0]}")

        # 4. Technical complexity from category
        category_lower = category.lower()
        if any(cat in category_lower for cat in self.COMPLEX_CATEGORIES):
            score += 1
            reasons.append(f"Complex category: {category}")

        # 5. Step content complexity
        complex_steps = sum(
            1 for step in steps
            if any(kw in step.lower() for kw in self.COMPLEX_STEP_KEYWORDS)
        )
        if complex_steps >= 3:
            score += 2
            reasons.append(f"Complex steps detected ({complex_steps} validation/integration steps)")
        elif complex_steps >= 1:
            score += 1
            reasons.append(f"Some complex steps ({complex_steps} steps)")

        # 6. Name complexity (UI redesign, full implementation, etc.)
        name_complexity_keywords = ["redesign", "full", "complete", "entire", "overhaul", "rebuild"]
        if any(kw in name_lower for kw in name_complexity_keywords):
            score += 1
            reasons.append("Feature name indicates significant scope")

        # Normalize score to 1-10 range
        score = max(1, min(10, score))

        # Determine level and approach
        if score >= self.COMPLEX_THRESHOLD:
            level = "complex"
            should_decompose = True
            suggested_approach = "require_decompose"
        elif score >= self.MEDIUM_THRESHOLD:
            level = "medium"
            should_decompose = True
            suggested_approach = "recommend_decompose"
        elif score >= self.SIMPLE_THRESHOLD:
            level = "medium"
            should_decompose = False
            suggested_approach = "recommend_decompose"
        else:
            level = "simple"
            should_decompose = False
            suggested_approach = "direct"

        return ComplexityAnalysis(
            score=score,
            level=level,
            should_decompose=should_decompose,
            reasons=reasons if reasons else ["Low complexity feature"],
            suggested_approach=suggested_approach,
        )

    def should_block_creation(self, analysis: ComplexityAnalysis) -> bool:
        """
        Check if feature creation should be blocked due to high complexity.

        Args:
            analysis: The complexity analysis result

        Returns:
            True if creation should be blocked, False otherwise
        """
        return analysis.suggested_approach == "require_decompose"

    def get_recommendation_message(self, analysis: ComplexityAnalysis) -> str:
        """
        Get a user-friendly recommendation message.

        Args:
            analysis: The complexity analysis result

        Returns:
            Human-readable recommendation
        """
        if analysis.suggested_approach == "require_decompose":
            return (
                f"This feature has a complexity score of {analysis.score}/10 and should be "
                "decomposed into smaller tasks using Skills Analysis before creation."
            )
        elif analysis.suggested_approach == "recommend_decompose":
            return (
                f"This feature has a complexity score of {analysis.score}/10. "
                "Consider using Skills Analysis to break it into smaller, more manageable tasks."
            )
        else:
            return "This feature has low complexity and can be created directly."


# Global instance with thread-safe initialization
_analyzer: Optional[ComplexityAnalyzer] = None
_analyzer_lock = threading.Lock()


def get_complexity_analyzer() -> ComplexityAnalyzer:
    """Get the global complexity analyzer instance."""
    global _analyzer

    with _analyzer_lock:
        if _analyzer is None:
            _analyzer = ComplexityAnalyzer()
        return _analyzer
