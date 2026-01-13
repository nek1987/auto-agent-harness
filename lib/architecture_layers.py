"""
Architecture Layers
===================

Defines project architectural layers and their dependencies for proper
implementation ordering. This ensures features are created and executed
in the correct sequence: foundation first, then features, then quality.

The layer system provides:
- Clear dependency hierarchy between project components
- Automatic mapping of feature categories to layers
- Support for the "Skeleton -> DB -> API -> Auth -> UI -> Features" workflow
"""

from enum import IntEnum
from typing import Optional


class ArchLayer(IntEnum):
    """
    Architectural layers in order of dependency.

    Lower numbers = earlier in implementation order.
    Each layer depends on all previous layers being at least partially complete.
    """

    SKELETON = 0  # Project structure, configs, package.json, tsconfig, etc.
    DATABASE = 1  # Schema definitions, migrations, ORM models
    BACKEND_CORE = 2  # API framework setup, routes structure, middleware
    AUTH = 3  # Authentication, authorization, session management
    BACKEND_FEATURES = 4  # API endpoints for business features
    FRONTEND_CORE = 5  # UI framework, routing, layout, navigation
    FRONTEND_FEATURES = 6  # UI components, pages, forms
    INTEGRATION = 7  # Full-stack features, workflows connecting UI and API
    QUALITY = 8  # Testing, security hardening, accessibility, performance


# Maps feature categories to their architectural layer.
# Categories not in this mapping default to QUALITY (layer 8).
CATEGORY_TO_LAYER: dict[str, ArchLayer] = {
    # Layer 0: SKELETON - Project foundation
    "project_setup": ArchLayer.SKELETON,
    "configuration": ArchLayer.SKELETON,
    "skeleton": ArchLayer.SKELETON,
    "setup": ArchLayer.SKELETON,
    "config": ArchLayer.SKELETON,
    "infrastructure": ArchLayer.SKELETON,
    # Layer 1: DATABASE - Data layer
    "database_schema": ArchLayer.DATABASE,
    "database": ArchLayer.DATABASE,
    "data_models": ArchLayer.DATABASE,
    "models": ArchLayer.DATABASE,
    "schema": ArchLayer.DATABASE,
    "migrations": ArchLayer.DATABASE,
    "orm": ArchLayer.DATABASE,
    # Layer 2: BACKEND_CORE - API foundation
    "api_structure": ArchLayer.BACKEND_CORE,
    "backend_setup": ArchLayer.BACKEND_CORE,
    "backend_core": ArchLayer.BACKEND_CORE,
    "api_core": ArchLayer.BACKEND_CORE,
    "middleware": ArchLayer.BACKEND_CORE,
    "routing": ArchLayer.BACKEND_CORE,
    # Layer 3: AUTH - Security layer
    "security": ArchLayer.AUTH,
    "authentication": ArchLayer.AUTH,
    "authorization": ArchLayer.AUTH,
    "auth": ArchLayer.AUTH,
    "access_control": ArchLayer.AUTH,
    "permissions": ArchLayer.AUTH,
    "session": ArchLayer.AUTH,
    # Layer 4: BACKEND_FEATURES - API features
    "api_endpoints": ArchLayer.BACKEND_FEATURES,
    "api": ArchLayer.BACKEND_FEATURES,
    "backend_features": ArchLayer.BACKEND_FEATURES,
    "business_logic": ArchLayer.BACKEND_FEATURES,
    "services": ArchLayer.BACKEND_FEATURES,
    "controllers": ArchLayer.BACKEND_FEATURES,
    # Layer 5: FRONTEND_CORE - UI foundation
    "ui_structure": ArchLayer.FRONTEND_CORE,
    "frontend_core": ArchLayer.FRONTEND_CORE,
    "navigation": ArchLayer.FRONTEND_CORE,
    "layout": ArchLayer.FRONTEND_CORE,
    "ui_core": ArchLayer.FRONTEND_CORE,
    "routing_ui": ArchLayer.FRONTEND_CORE,
    # Layer 6: FRONTEND_FEATURES - UI features
    "ui_components": ArchLayer.FRONTEND_FEATURES,
    "frontend_features": ArchLayer.FRONTEND_FEATURES,
    "forms": ArchLayer.FRONTEND_FEATURES,
    "pages": ArchLayer.FRONTEND_FEATURES,
    "components": ArchLayer.FRONTEND_FEATURES,
    "views": ArchLayer.FRONTEND_FEATURES,
    "ui": ArchLayer.FRONTEND_FEATURES,
    # Layer 7: INTEGRATION - Full-stack features
    "workflow": ArchLayer.INTEGRATION,
    "integration": ArchLayer.INTEGRATION,
    "full_stack": ArchLayer.INTEGRATION,
    "end_to_end": ArchLayer.INTEGRATION,
    "crud": ArchLayer.INTEGRATION,
    "data_flow": ArchLayer.INTEGRATION,
    # Layer 8: QUALITY - Non-functional requirements
    "error_handling": ArchLayer.QUALITY,
    "validation": ArchLayer.QUALITY,
    "accessibility": ArchLayer.QUALITY,
    "performance": ArchLayer.QUALITY,
    "responsive": ArchLayer.QUALITY,
    "testing": ArchLayer.QUALITY,
    "quality": ArchLayer.QUALITY,
    "functional": ArchLayer.QUALITY,  # Legacy category
    "style": ArchLayer.QUALITY,  # Legacy category
}

# Human-readable names for layers
LAYER_NAMES: dict[ArchLayer, str] = {
    ArchLayer.SKELETON: "Project Skeleton & Config",
    ArchLayer.DATABASE: "Database Schema & Models",
    ArchLayer.BACKEND_CORE: "Backend Core (API structure)",
    ArchLayer.AUTH: "Authentication & Authorization",
    ArchLayer.BACKEND_FEATURES: "Backend API Endpoints",
    ArchLayer.FRONTEND_CORE: "Frontend Core (Layout, Nav)",
    ArchLayer.FRONTEND_FEATURES: "Frontend Features (Pages, UI)",
    ArchLayer.INTEGRATION: "Integration & Workflows",
    ArchLayer.QUALITY: "Quality (Testing, A11y, Perf)",
}


def get_layer_for_category(category: str) -> ArchLayer:
    """
    Get the architectural layer for a feature category.

    Args:
        category: Feature category string (case-insensitive)

    Returns:
        The ArchLayer for this category, defaults to QUALITY if unknown.
    """
    normalized = category.lower().strip().replace(" ", "_").replace("-", "_")
    return CATEGORY_TO_LAYER.get(normalized, ArchLayer.QUALITY)


def get_layer_name(layer: ArchLayer) -> str:
    """
    Get human-readable name for a layer.

    Args:
        layer: The architectural layer

    Returns:
        Human-readable layer name
    """
    return LAYER_NAMES.get(layer, f"Layer {layer}")


def get_required_layers(layer: ArchLayer) -> list[ArchLayer]:
    """
    Get all layers that must be complete before working on this layer.

    Args:
        layer: The target layer

    Returns:
        List of prerequisite layers (all layers with lower numbers)
    """
    return [l for l in ArchLayer if l < layer]


def is_layer_blocked(
    target_layer: ArchLayer,
    completed_layers: set[ArchLayer],
    partial_threshold: float = 0.8,
) -> bool:
    """
    Check if a layer is blocked by incomplete prerequisite layers.

    Args:
        target_layer: The layer we want to work on
        completed_layers: Set of layers that are at least partially complete
        partial_threshold: Minimum completion ratio to consider a layer "ready"
                          (not used here, but available for future enhancement)

    Returns:
        True if any prerequisite layer is not in completed_layers
    """
    required = get_required_layers(target_layer)
    return not all(layer in completed_layers for layer in required)


def suggest_next_layer(completed_layers: set[ArchLayer]) -> Optional[ArchLayer]:
    """
    Suggest the next layer to work on based on completed layers.

    Args:
        completed_layers: Set of layers that are complete

    Returns:
        The next layer to work on, or None if all layers complete
    """
    for layer in ArchLayer:
        if layer not in completed_layers:
            # Check if prerequisites are met
            if not is_layer_blocked(layer, completed_layers):
                return layer
    return None
