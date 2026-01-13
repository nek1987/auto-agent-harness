"""
Layer Validator
===============

Validates that features respect architectural layer dependencies.
Provides warnings when features are created or executed out of order,
and utilities for checking layer completion status.

This module helps ensure the correct implementation order:
Skeleton -> DB -> API -> Auth -> UI -> Features
"""

from dataclasses import dataclass
from typing import Protocol, Optional
from collections import defaultdict

from .architecture_layers import (
    ArchLayer,
    get_layer_name,
    get_layer_for_category,
    get_required_layers,
)


class FeatureLike(Protocol):
    """Protocol for feature objects that can be layer-validated."""

    id: int
    priority: int
    passes: bool
    category: str
    name: str
    arch_layer: Optional[int]


@dataclass
class LayerStats:
    """Statistics for a single architectural layer."""

    layer: ArchLayer
    total: int = 0
    passing: int = 0
    in_progress: int = 0

    @property
    def completion_ratio(self) -> float:
        """Get the completion ratio (0.0 to 1.0)."""
        if self.total == 0:
            return 1.0  # Empty layer is considered complete
        return self.passing / self.total

    @property
    def is_complete(self) -> bool:
        """Check if layer is fully complete."""
        return self.passing == self.total

    @property
    def is_ready(self, threshold: float = 0.8) -> bool:
        """Check if layer is sufficiently complete (default 80%)."""
        return self.completion_ratio >= threshold


@dataclass
class LayerValidationResult:
    """Result of layer order validation."""

    is_valid: bool
    warnings: list[str]
    blocking_layers: list[ArchLayer]
    stats_by_layer: dict[ArchLayer, LayerStats]


def validate_feature_order(features: list[FeatureLike]) -> list[str]:
    """
    Validate that features are in correct architectural order.

    Checks if features with higher priority numbers have lower layer numbers,
    which would indicate they're being executed before their dependencies.

    Args:
        features: List of feature objects with arch_layer and priority

    Returns:
        List of warning messages for out-of-order features
    """
    warnings = []
    sorted_features = sorted(features, key=lambda x: x.priority)
    max_layer_seen = -1

    for f in sorted_features:
        feature_layer = f.arch_layer if f.arch_layer is not None else 8

        if feature_layer < max_layer_seen:
            warnings.append(
                f"Feature '{f.name}' (id={f.id}, layer={feature_layer}) "
                f"has lower layer than previously scheduled features "
                f"(max layer seen: {max_layer_seen}). "
                f"This may cause dependency issues."
            )

        max_layer_seen = max(max_layer_seen, feature_layer)

    return warnings


def get_layer_stats(features: list[FeatureLike]) -> dict[ArchLayer, LayerStats]:
    """
    Calculate completion statistics for each architectural layer.

    Args:
        features: List of feature objects

    Returns:
        Dictionary mapping layers to their statistics
    """
    stats: dict[ArchLayer, LayerStats] = {
        layer: LayerStats(layer=layer) for layer in ArchLayer
    }

    for f in features:
        layer = ArchLayer(f.arch_layer) if f.arch_layer is not None else ArchLayer.QUALITY
        stats[layer].total += 1
        if f.passes:
            stats[layer].passing += 1

    return stats


def get_blocking_layers(
    target_layer: ArchLayer,
    features: list[FeatureLike],
    threshold: float = 0.8,
) -> list[ArchLayer]:
    """
    Get layers that must be more complete before working on target layer.

    A layer is considered "blocking" if it has less than threshold completion
    and is a prerequisite for the target layer.

    Args:
        target_layer: The layer we want to work on
        features: List of all features
        threshold: Minimum completion ratio (0.0-1.0) to not be blocking

    Returns:
        List of blocking layer numbers
    """
    stats = get_layer_stats(features)
    blocking = []

    for required_layer in get_required_layers(target_layer):
        layer_stats = stats[required_layer]
        if layer_stats.completion_ratio < threshold:
            blocking.append(required_layer)

    return blocking


def validate_layer_dependencies(
    feature: FeatureLike,
    all_features: list[FeatureLike],
    threshold: float = 0.8,
) -> LayerValidationResult:
    """
    Validate if a feature can be worked on based on layer dependencies.

    Args:
        feature: The feature to validate
        all_features: List of all features in the project
        threshold: Minimum completion ratio for prerequisite layers

    Returns:
        LayerValidationResult with validation status and details
    """
    feature_layer = (
        ArchLayer(feature.arch_layer)
        if feature.arch_layer is not None
        else ArchLayer.QUALITY
    )

    stats = get_layer_stats(all_features)
    blocking = get_blocking_layers(feature_layer, all_features, threshold)

    warnings = []
    if blocking:
        blocking_names = [get_layer_name(l) for l in blocking]
        warnings.append(
            f"Feature '{feature.name}' is in layer {feature_layer} "
            f"({get_layer_name(feature_layer)}), but prerequisite layers "
            f"are not sufficiently complete: {', '.join(blocking_names)}"
        )

    return LayerValidationResult(
        is_valid=len(blocking) == 0,
        warnings=warnings,
        blocking_layers=blocking,
        stats_by_layer=stats,
    )


def suggest_skip_reason(
    feature: FeatureLike,
    all_features: list[FeatureLike],
    threshold: float = 0.8,
) -> Optional[str]:
    """
    Generate a skip reason if feature should be skipped due to layer dependencies.

    Args:
        feature: The feature to check
        all_features: List of all features
        threshold: Minimum completion ratio for prerequisite layers

    Returns:
        Skip reason string, or None if feature is ready to implement
    """
    result = validate_layer_dependencies(feature, all_features, threshold)

    if result.is_valid:
        return None

    blocking_names = [get_layer_name(l) for l in result.blocking_layers]
    return (
        f"Waiting for prerequisite layers to complete: {', '.join(blocking_names)}. "
        f"Feature '{feature.name}' is in layer {get_layer_name(ArchLayer(feature.arch_layer or 8))}."
    )


def get_layer_progress_summary(features: list[FeatureLike]) -> str:
    """
    Generate a human-readable summary of layer completion progress.

    Args:
        features: List of all features

    Returns:
        Multi-line string showing progress per layer
    """
    stats = get_layer_stats(features)
    lines = ["Layer Progress:"]

    for layer in ArchLayer:
        s = stats[layer]
        if s.total == 0:
            status = "N/A"
        elif s.is_complete:
            status = "COMPLETE"
        else:
            pct = int(s.completion_ratio * 100)
            status = f"{s.passing}/{s.total} ({pct}%)"

        lines.append(f"  {layer.value}. {get_layer_name(layer)}: {status}")

    return "\n".join(lines)


def auto_assign_layer(category: str, existing_layer: Optional[int] = None) -> int:
    """
    Auto-assign architectural layer based on category.

    If existing_layer is provided and valid, returns it unchanged.
    Otherwise, infers layer from category name.

    Args:
        category: Feature category string
        existing_layer: Existing layer value (if any)

    Returns:
        Architectural layer number (0-8)
    """
    if existing_layer is not None and 0 <= existing_layer <= 8:
        return existing_layer

    return int(get_layer_for_category(category))
