"""
Feature Splitter
================

Automatically splits complex features (10+ steps) into smaller, more manageable
sub-features. This improves implementation success rate by breaking down large
tasks into focused, independently testable units.

The splitter analyzes step content and groups them by logical operations:
- Navigation / Setup
- Form Input
- API Calls
- Verification
- etc.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SplitResult:
    """Result of feature splitting operation."""

    original_count: int
    final_count: int
    split_count: int  # Number of features that were split
    features: list[dict]


class FeatureSplitter:
    """
    Automatically splits complex features into smaller sub-features.

    Features with more than COMPLEXITY_THRESHOLD steps are analyzed
    and split into logical groups based on step content.
    """

    COMPLEXITY_THRESHOLD = 10  # Steps threshold for splitting
    MIN_GROUP_SIZE = 2  # Minimum steps per sub-feature

    # Keywords for grouping steps by operation type
    STEP_KEYWORDS: dict[str, list[str]] = {
        "Navigation": ["navigate", "go to", "open", "visit", "load"],
        "Form Input": ["fill", "enter", "input", "type", "select", "choose"],
        "Submission": ["submit", "save", "create", "send", "post"],
        "Verification": ["verify", "check", "assert", "confirm", "ensure", "should"],
        "Interaction": ["click", "press", "tap", "toggle", "expand", "collapse"],
        "API Call": ["api", "request", "fetch", "call", "endpoint"],
        "Database": ["database", "db", "query", "insert", "update", "delete"],
        "Wait": ["wait", "delay", "pause", "sleep"],
        "Screenshot": ["screenshot", "capture", "visual"],
    }

    def analyze_and_split(
        self, features: list[dict], auto_split: bool = True
    ) -> SplitResult:
        """
        Analyze features and split complex ones into sub-features.

        Args:
            features: List of feature dictionaries with name, category, steps, etc.
            auto_split: If False, only analyze but don't split

        Returns:
            SplitResult with original count, final count, and processed features
        """
        if not auto_split:
            return SplitResult(
                original_count=len(features),
                final_count=len(features),
                split_count=0,
                features=features,
            )

        result_features = []
        split_count = 0

        for feature in features:
            steps = feature.get("steps", [])

            if len(steps) >= self.COMPLEXITY_THRESHOLD:
                sub_features = self._split_feature(feature)
                if len(sub_features) > 1:
                    result_features.extend(sub_features)
                    split_count += 1
                    logger.info(
                        f"Split feature '{feature.get('name', 'Unknown')}' "
                        f"({len(steps)} steps) into {len(sub_features)} sub-features"
                    )
                else:
                    # Couldn't split meaningfully, keep original
                    result_features.append(feature)
            else:
                result_features.append(feature)

        return SplitResult(
            original_count=len(features),
            final_count=len(result_features),
            split_count=split_count,
            features=result_features,
        )

    def _split_feature(self, feature: dict) -> list[dict]:
        """
        Split a single feature into sub-features based on step grouping.

        Args:
            feature: Feature dictionary with steps

        Returns:
            List of sub-feature dictionaries (may be single item if can't split)
        """
        steps = feature.get("steps", [])
        name = feature.get("name", "Feature")
        category = feature.get("category", "workflow")
        description = feature.get("description", "")

        # Group steps by logical operations
        groups = self._group_steps(steps)

        # If we ended up with just one group, try alternative splitting
        if len(groups) <= 1:
            groups = self._split_by_count(steps)

        # If still can't split meaningfully, return original
        if len(groups) <= 1:
            return [feature]

        # Create sub-features from groups
        sub_features = []
        for i, (group_name, group_steps) in enumerate(groups.items()):
            if len(group_steps) < self.MIN_GROUP_SIZE:
                continue

            sub_feature = {
                "category": category,
                "name": f"{name} - {group_name}",
                "description": f"Part {i + 1}/{len(groups)}: {group_name}. {description}",
                "steps": group_steps,
                "parent_feature_name": name,
            }

            # Preserve any additional fields from original
            for key in ["dependencies", "arch_layer", "priority"]:
                if key in feature:
                    sub_feature[key] = feature[key]

            sub_features.append(sub_feature)

        # If splitting resulted in fewer than 2 sub-features, return original
        if len(sub_features) < 2:
            return [feature]

        return sub_features

    def _group_steps(self, steps: list[str]) -> dict[str, list[str]]:
        """
        Group steps by logical operation type based on keywords.

        Args:
            steps: List of step descriptions

        Returns:
            Dictionary mapping group names to lists of steps
        """
        groups: dict[str, list[str]] = {}
        current_group = "Setup"
        current_steps: list[str] = []

        for step in steps:
            step_lower = step.lower()

            # Find matching keyword group
            matched_group: Optional[str] = None
            for group_name, keywords in self.STEP_KEYWORDS.items():
                if any(kw in step_lower for kw in keywords):
                    matched_group = group_name
                    break

            if matched_group and matched_group != current_group:
                # Save current group if it has steps
                if current_steps:
                    if current_group in groups:
                        groups[current_group].extend(current_steps)
                    else:
                        groups[current_group] = current_steps

                current_group = matched_group
                current_steps = [step]
            else:
                current_steps.append(step)

        # Save final group
        if current_steps:
            if current_group in groups:
                groups[current_group].extend(current_steps)
            else:
                groups[current_group] = current_steps

        return groups

    def _split_by_count(self, steps: list[str], max_per_group: int = 7) -> dict[str, list[str]]:
        """
        Split steps by count when keyword grouping doesn't work well.

        Args:
            steps: List of step descriptions
            max_per_group: Maximum steps per group

        Returns:
            Dictionary mapping group names to lists of steps
        """
        groups: dict[str, list[str]] = {}
        total_groups = (len(steps) + max_per_group - 1) // max_per_group

        for i in range(total_groups):
            start = i * max_per_group
            end = min((i + 1) * max_per_group, len(steps))
            group_name = f"Part {i + 1}"
            groups[group_name] = steps[start:end]

        return groups

    def estimate_complexity(self, feature: dict) -> str:
        """
        Estimate feature complexity based on step count and content.

        Args:
            feature: Feature dictionary

        Returns:
            Complexity level: "simple", "medium", or "complex"
        """
        steps = feature.get("steps", [])
        step_count = len(steps)

        if step_count < 5:
            return "simple"
        elif step_count < self.COMPLEXITY_THRESHOLD:
            return "medium"
        else:
            return "complex"

    def get_split_recommendation(self, feature: dict) -> dict:
        """
        Get recommendation for how to split a feature.

        Args:
            feature: Feature dictionary

        Returns:
            Dictionary with recommendation details
        """
        steps = feature.get("steps", [])
        complexity = self.estimate_complexity(feature)

        if complexity != "complex":
            return {
                "should_split": False,
                "complexity": complexity,
                "reason": "Feature has acceptable complexity",
            }

        groups = self._group_steps(steps)

        return {
            "should_split": True,
            "complexity": complexity,
            "step_count": len(steps),
            "suggested_groups": len(groups),
            "group_names": list(groups.keys()),
            "reason": f"Feature has {len(steps)} steps, recommend splitting into {len(groups)} sub-features",
        }


# Module-level function for easy access
def split_features(features: list[dict], auto_split: bool = True) -> SplitResult:
    """
    Split complex features into smaller sub-features.

    Args:
        features: List of feature dictionaries
        auto_split: If True, automatically split complex features

    Returns:
        SplitResult with processed features
    """
    splitter = FeatureSplitter()
    return splitter.analyze_and_split(features, auto_split)
