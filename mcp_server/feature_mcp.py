#!/usr/bin/env python3
"""
MCP Server for Feature Management
==================================

Provides tools to manage features in the autonomous coding system,
replacing the previous FastAPI-based REST API.

Tools:
- feature_get_stats: Get progress statistics
- feature_get_next: Get next feature to implement
- feature_get_for_regression: Get random passing features for testing
- feature_mark_passing: Mark a feature as passing
- feature_skip: Skip a feature (move to end of queue)
- feature_mark_in_progress: Mark a feature as in-progress
- feature_clear_in_progress: Clear in-progress status
- feature_create_bulk: Create multiple features at once
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy.sql.expression import func

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import Feature, create_database
from api.migration import migrate_json_to_sqlite
from lib.architecture_layers import get_layer_for_category, ArchLayer, get_layer_name
from lib.feature_splitter import FeatureSplitter, split_features
from lib.completion_reporter import CompletionReporter, check_project_completion

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()


# Pydantic models for input validation
class MarkPassingInput(BaseModel):
    """Input for marking a feature as passing."""
    feature_id: int = Field(..., description="The ID of the feature to mark as passing", ge=1)


class SkipFeatureInput(BaseModel):
    """Input for skipping a feature."""
    feature_id: int = Field(..., description="The ID of the feature to skip", ge=1)


class MarkInProgressInput(BaseModel):
    """Input for marking a feature as in-progress."""
    feature_id: int = Field(..., description="The ID of the feature to mark as in-progress", ge=1)


class ClearInProgressInput(BaseModel):
    """Input for clearing in-progress status."""
    feature_id: int = Field(..., description="The ID of the feature to clear in-progress status", ge=1)


class RegressionInput(BaseModel):
    """Input for getting regression features."""
    limit: int = Field(default=3, ge=1, le=10, description="Maximum number of passing features to return")


class FeatureCreateItem(BaseModel):
    """Schema for creating a single feature."""
    category: str = Field(..., min_length=1, max_length=100, description="Feature category")
    name: str = Field(..., min_length=1, max_length=255, description="Feature name")
    description: str = Field(..., min_length=1, description="Detailed description")
    steps: list[str] = Field(..., min_length=1, description="Implementation/test steps")


class BulkCreateInput(BaseModel):
    """Input for bulk creating features."""
    features: list[FeatureCreateItem] = Field(..., min_length=1, description="List of features to create")


class FeatureImportItem(BaseModel):
    """Schema for importing a feature with status."""
    category: str = Field(..., min_length=1, max_length=100, description="Feature category")
    name: str = Field(..., min_length=1, max_length=255, description="Feature name")
    description: str = Field(..., min_length=1, description="Detailed description")
    steps: list[str] = Field(default_factory=lambda: ["Verify implementation"], description="Implementation/test steps")
    passes: bool = Field(default=True, description="Whether feature is already implemented (default: True)")
    source_spec: str = Field(default="imported", max_length=100, description="Source spec name")
    dependencies: list[int] | None = Field(default=None, description="List of feature IDs this depends on")


# Global database session maker (initialized on startup)
_session_maker = None
_engine = None


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize database on startup, cleanup on shutdown."""
    global _session_maker, _engine

    # Create project directory if it doesn't exist
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    _engine, _session_maker = create_database(PROJECT_DIR)

    # Run migration if needed (converts legacy JSON to SQLite)
    migrate_json_to_sqlite(PROJECT_DIR, _session_maker)

    yield

    # Cleanup
    if _engine:
        _engine.dispose()


# Initialize the MCP server
mcp = FastMCP("features", lifespan=server_lifespan)


def get_session():
    """Get a new database session."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized")
    return _session_maker()


@mcp.tool()
def feature_get_stats() -> str:
    """Get statistics about feature completion progress.

    Returns the number of passing features, in-progress features, total features,
    and completion percentage. Use this to track overall progress of the implementation.

    Returns:
        JSON with: passing (int), in_progress (int), total (int), percentage (float)
    """
    session = get_session()
    try:
        total = session.query(Feature).count()
        passing = session.query(Feature).filter(Feature.passes == True).count()
        in_progress = session.query(Feature).filter(Feature.in_progress == True).count()
        percentage = round((passing / total) * 100, 1) if total > 0 else 0.0

        return json.dumps({
            "passing": passing,
            "in_progress": in_progress,
            "total": total,
            "percentage": percentage
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_next() -> str:
    """Get the next item to work on, prioritizing redesign, bugs, and their fixes.

    Priority order:
    0. Redesign tasks (item_type='redesign') - highest priority, apply design tokens
    1. Open bugs (item_type='bug', bug_status='open') - need analysis
    2. Bug fix features (parent_bug_id is set) - derived from bug analysis
    3. Regular features - ordered by arch_layer FIRST, then priority
       (ensures foundation layers are built before features)

    Architectural layer order (0-8):
    0=Skeleton, 1=Database, 2=Backend Core, 3=Auth, 4=Backend Features,
    5=Frontend Core, 6=Frontend Features, 7=Integration, 8=Quality

    When a bug is returned, analyze it and create fix features using feature_create_bulk
    with parent_bug_id set.

    Returns:
        JSON with:
        - type: 'redesign' | 'bug_analysis_needed' | 'bug_fix' | 'feature' | 'all_done'
        - For redesign: session_id and instructions to apply design tokens
        - For bugs: instruction to analyze and create fix features
        - For features: standard feature details with arch_layer info
    """
    session = get_session()
    try:
        # 0. First check for redesign tasks (highest priority - design system changes)
        redesign_task = (
            session.query(Feature)
            .filter(
                Feature.item_type == "redesign",
                Feature.passes == False,
                Feature.in_progress == False,
            )
            .order_by(Feature.priority.asc(), Feature.id.asc())
            .first()
        )

        if redesign_task:
            return json.dumps({
                "type": "redesign",
                "feature": redesign_task.to_dict(),
                "redesign_session_id": redesign_task.redesign_session_id,
                "instruction": (
                    "Apply design tokens from the redesign session. Steps:\n"
                    "1. Mark this feature as in_progress using feature_mark_in_progress\n"
                    "2. Get design tokens: redesign_get_tokens\n"
                    "3. Get change plan: redesign_get_plan\n"
                    "4. For each approved phase, apply file changes using Edit tool\n"
                    "5. Complete redesign: redesign_complete_session\n"
                    "6. Mark this feature as passing: feature_mark_passing"
                )
            }, indent=2)

        # 1. Then check for open bugs that need analysis
        bug = (
            session.query(Feature)
            .filter(
                Feature.item_type == "bug",
                Feature.bug_status == "open",
                Feature.passes == False
            )
            .order_by(Feature.priority.asc(), Feature.id.asc())
            .first()
        )

        if bug:
            # Mark bug as being analyzed
            bug.bug_status = "analyzing"
            session.commit()
            session.refresh(bug)

            return json.dumps({
                "type": "bug_analysis_needed",
                "bug": bug.to_dict(),
                "instruction": (
                    "Analyze this bug and create fix features using feature_create_bulk. "
                    "Include 'parent_bug_id': " + str(bug.id) + " in each fix feature. "
                    "After creating fixes, the bug status will be 'fixing'."
                )
            }, indent=2)

        # 2. Then check for bug fix features (highest priority after bug analysis)
        fix_feature = (
            session.query(Feature)
            .filter(
                Feature.passes == False,
                Feature.in_progress == False,
                Feature.parent_bug_id != None
            )
            .order_by(Feature.priority.asc(), Feature.id.asc())
            .first()
        )

        if fix_feature:
            return json.dumps({
                "type": "bug_fix",
                "feature": fix_feature.to_dict(),
                "parent_bug_id": fix_feature.parent_bug_id,
                "instruction": "This is a fix for bug #" + str(fix_feature.parent_bug_id) + ". Implement and test carefully."
            }, indent=2)

        # 3. Finally check for regular features
        # ORDER BY arch_layer ASC ensures foundation layers (0-3) come before feature layers (4-8)
        feature = (
            session.query(Feature)
            .filter(
                Feature.passes == False,
                Feature.in_progress == False,
                Feature.item_type == "feature"
            )
            .order_by(
                Feature.arch_layer.asc(),  # Foundation first, then features, then quality
                Feature.priority.asc(),     # Within same layer, use priority
                Feature.id.asc()            # Tie-breaker
            )
            .first()
        )

        if feature:
            # Add layer info to help agent understand context
            layer_num = feature.arch_layer if feature.arch_layer is not None else 8
            layer_name = get_layer_name(ArchLayer(layer_num))

            return json.dumps({
                "type": "feature",
                "feature": feature.to_dict(),
                "layer_info": {
                    "layer": layer_num,
                    "layer_name": layer_name,
                    "hint": f"This is a {layer_name} feature (layer {layer_num}/8)"
                }
            }, indent=2)

        # 4. Check if there are any non-passing features at all
        any_pending = session.query(Feature).filter(Feature.passes == False).first()
        if any_pending:
            return json.dumps({
                "type": "in_progress",
                "message": "All pending features are currently in-progress. Wait or use feature_clear_in_progress."
            })

        return json.dumps({
            "type": "all_done",
            "message": "All features are passing! No more work to do."
        })
    finally:
        session.close()


@mcp.tool()
def feature_get_for_regression(
    limit: Annotated[int, Field(default=3, ge=1, le=10, description="Maximum number of passing features to return")] = 3
) -> str:
    """Get random passing features for regression testing.

    Returns a random selection of features that are currently passing.
    Use this to verify that previously implemented features still work
    after making changes.

    Args:
        limit: Maximum number of features to return (1-10, default 3)

    Returns:
        JSON with: features (list of feature objects), count (int)
    """
    session = get_session()
    try:
        features = (
            session.query(Feature)
            .filter(Feature.passes == True)
            .order_by(func.random())
            .limit(limit)
            .all()
        )

        return json.dumps({
            "features": [f.to_dict() for f in features],
            "count": len(features)
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_mark_passing(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as passing", ge=1)]
) -> str:
    """Mark a feature as passing after successful implementation.

    Updates the feature's passes field to true and clears the in_progress flag.
    Use this after you have implemented the feature and verified it works correctly.

    Args:
        feature_id: The ID of the feature to mark as passing

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.passes = True
        feature.in_progress = False
        session.commit()
        session.refresh(feature)

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_skip(
    feature_id: Annotated[int, Field(description="The ID of the feature to skip", ge=1)]
) -> str:
    """Skip a feature by moving it to the end of the priority queue.

    Use this when a feature cannot be implemented yet due to:
    - Dependencies on other features that aren't implemented yet
    - External blockers (missing assets, unclear requirements)
    - Technical prerequisites that need to be addressed first

    The feature's priority is set to max_priority + 1, so it will be
    worked on after all other pending features. Also clears the in_progress
    flag so the feature returns to "pending" status.

    Args:
        feature_id: The ID of the feature to skip

    Returns:
        JSON with skip details: id, name, old_priority, new_priority, message
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps({"error": "Cannot skip a feature that is already passing"})

        old_priority = feature.priority

        # Get max priority and set this feature to max + 1
        max_priority_result = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
        new_priority = (max_priority_result[0] + 1) if max_priority_result else 1

        feature.priority = new_priority
        feature.in_progress = False
        session.commit()
        session.refresh(feature)

        return json.dumps({
            "id": feature.id,
            "name": feature.name,
            "old_priority": old_priority,
            "new_priority": new_priority,
            "message": f"Feature '{feature.name}' moved to end of queue"
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_mark_in_progress(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as in-progress", ge=1)]
) -> str:
    """Mark a feature as in-progress. Call immediately after feature_get_next().

    This prevents other agent sessions from working on the same feature.
    Use this as soon as you retrieve a feature to work on.

    Args:
        feature_id: The ID of the feature to mark as in-progress

    Returns:
        JSON with the updated feature details, or error if not found or already in-progress.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps({"error": f"Feature with ID {feature_id} is already passing"})

        if feature.in_progress:
            return json.dumps({"error": f"Feature with ID {feature_id} is already in-progress"})

        feature.in_progress = True
        session.commit()
        session.refresh(feature)

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_clear_in_progress(
    feature_id: Annotated[int, Field(description="The ID of the feature to clear in-progress status", ge=1)]
) -> str:
    """Clear in-progress status from a feature.

    Use this when abandoning a feature or manually unsticking a stuck feature.
    The feature will return to the pending queue.

    Args:
        feature_id: The ID of the feature to clear in-progress status

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.in_progress = False
        session.commit()
        session.refresh(feature)

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_create_bulk(
    features: Annotated[list[dict], Field(description="List of features to create, each with category, name, description, and steps")],
    auto_split: Annotated[bool, Field(description="Auto-split complex features with 10+ steps into sub-features")] = True
) -> str:
    """Create multiple features in a single operation.

    Features are assigned sequential priorities based on their order.
    All features start with passes=false.
    Architectural layer (arch_layer) is auto-assigned based on category.

    AUTOMATIC SPLITTING: By default, features with 10+ steps are automatically
    split into smaller sub-features for better manageability. Set auto_split=false
    to disable this behavior.

    This is typically used by:
    - Initializer agent to set up features from app specification
    - Bug analyzer to create fix features (include parent_bug_id)

    Architectural layers (auto-assigned by category):
    - 0: skeleton, setup, config, infrastructure
    - 1: database, schema, models, migrations
    - 2: backend_core, api_structure, middleware
    - 3: auth, security, authentication, authorization
    - 4: api_endpoints, backend_features, services
    - 5: frontend_core, navigation, layout
    - 6: ui_components, frontend_features, forms, pages
    - 7: workflow, integration, full_stack
    - 8: quality, error_handling, validation, accessibility, performance (default)

    Args:
        features: List of features to create, each with:
            - category (str): Feature category (determines arch_layer)
            - name (str): Feature name
            - description (str): Detailed description
            - steps (list[str]): Implementation/test steps
            - parent_bug_id (int, optional): Bug ID if this is a fix feature
            - arch_layer (int, optional): Override auto-assigned layer (0-8)
        auto_split: If True (default), features with 10+ steps are auto-split

    Returns:
        JSON with: created (int), bug_fixes (int), layers_summary, split_info
    """
    session = get_session()
    try:
        # Auto-split complex features if enabled
        split_info = None
        if auto_split:
            result = split_features(features, auto_split=True)
            if result.split_count > 0:
                split_info = {
                    "original_count": result.original_count,
                    "after_split": result.final_count,
                    "features_split": result.split_count,
                }
            features = result.features
        # Get the starting priority
        max_priority_result = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
        start_priority = (max_priority_result[0] + 1) if max_priority_result else 1

        created_count = 0
        bug_fix_count = 0
        parent_bug_ids = set()
        layers_summary = {}  # Track features per layer

        for i, feature_data in enumerate(features):
            # Validate required fields
            if not all(key in feature_data for key in ["category", "name", "description", "steps"]):
                return json.dumps({
                    "error": f"Feature at index {i} missing required fields (category, name, description, steps)"
                })

            parent_bug_id = feature_data.get("parent_bug_id")
            if parent_bug_id:
                parent_bug_ids.add(parent_bug_id)
                bug_fix_count += 1

            # Auto-assign architectural layer based on category
            category = feature_data["category"]
            explicit_layer = feature_data.get("arch_layer")

            if explicit_layer is not None and 0 <= explicit_layer <= 8:
                arch_layer = explicit_layer
            else:
                arch_layer = int(get_layer_for_category(category))

            # Track layers for summary
            layer_name = get_layer_name(ArchLayer(arch_layer))
            if layer_name not in layers_summary:
                layers_summary[layer_name] = 0
            layers_summary[layer_name] += 1

            db_feature = Feature(
                priority=start_priority + i,
                category=category,
                name=feature_data["name"],
                description=feature_data["description"],
                steps=feature_data["steps"],
                passes=False,
                item_type="feature",
                parent_bug_id=parent_bug_id,
                arch_layer=arch_layer,
            )
            session.add(db_feature)
            created_count += 1

        # Update bug status to 'fixing' if we created fix features
        for bug_id in parent_bug_ids:
            bug = session.query(Feature).filter(Feature.id == bug_id).first()
            if bug and bug.item_type == "bug":
                bug.bug_status = "fixing"

        session.commit()

        result = {
            "created": created_count,
            "layers_summary": layers_summary,
        }
        if split_info:
            result["split_info"] = split_info
        if bug_fix_count > 0:
            result["bug_fixes"] = bug_fix_count
            result["parent_bugs"] = list(parent_bug_ids)
            result["message"] = f"Created {bug_fix_count} fix features for bug(s) {list(parent_bug_ids)}"

        return json.dumps(result, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_import_existing(
    features: Annotated[list[dict], Field(description="List of features to import with status")]
) -> str:
    """Import features from an existing project with pre-set statuses.

    Unlike feature_create_bulk, this tool allows importing features that are
    already implemented (passes=true by default). Use this when:
    - Importing an existing project into the harness
    - Migrating features from another system
    - Setting up a project with known completed work

    Features are assigned sequential priorities based on their order.

    Args:
        features: List of features to import, each with:
            - category (str): Feature category (required)
            - name (str): Feature name (required)
            - description (str): Detailed description (required)
            - steps (list[str]): Implementation/test steps (optional, defaults to ["Verify implementation"])
            - passes (bool): Whether already implemented (optional, defaults to True)
            - source_spec (str): Source spec name (optional, defaults to "imported")
            - dependencies (list[int]): Feature IDs this depends on (optional)

    Returns:
        JSON with: imported (int), passing (int), pending (int)
    """
    session = get_session()
    try:
        # Get the starting priority
        max_priority_result = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
        start_priority = (max_priority_result[0] + 1) if max_priority_result else 1

        imported_count = 0
        passing_count = 0
        pending_count = 0

        for i, feature_data in enumerate(features):
            # Validate required fields
            if not all(key in feature_data for key in ["category", "name", "description"]):
                return json.dumps({
                    "error": f"Feature at index {i} missing required fields (category, name, description)"
                })

            # Extract values with defaults
            passes = feature_data.get("passes", True)
            source_spec = feature_data.get("source_spec", "imported")
            steps = feature_data.get("steps", ["Verify implementation"])
            dependencies = feature_data.get("dependencies")

            db_feature = Feature(
                priority=start_priority + i,
                category=feature_data["category"],
                name=feature_data["name"],
                description=feature_data["description"],
                steps=steps,
                passes=passes,
                in_progress=False,
                source_spec=source_spec,
                dependencies=dependencies,
            )
            session.add(db_feature)
            imported_count += 1

            if passes:
                passing_count += 1
            else:
                pending_count += 1

        session.commit()

        return json.dumps({
            "imported": imported_count,
            "passing": passing_count,
            "pending": pending_count,
            "message": f"Imported {imported_count} features ({passing_count} passing, {pending_count} pending)"
        }, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_bulk_mark_passing(
    feature_ids: Annotated[list[int], Field(description="List of feature IDs to mark as passing")]
) -> str:
    """Mark multiple features as passing in a single operation.

    Use this when importing an existing project where multiple features
    are already implemented and need to be marked as passing at once.

    Args:
        feature_ids: List of feature IDs to mark as passing

    Returns:
        JSON with: updated (int), not_found (list[int]), already_passing (list[int])
    """
    session = get_session()
    try:
        updated_count = 0
        not_found = []
        already_passing = []

        for feature_id in feature_ids:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if feature is None:
                not_found.append(feature_id)
                continue

            if feature.passes:
                already_passing.append(feature_id)
                continue

            feature.passes = True
            feature.in_progress = False
            updated_count += 1

        session.commit()

        return json.dumps({
            "updated": updated_count,
            "not_found": not_found,
            "already_passing": already_passing,
            "message": f"Marked {updated_count} features as passing"
        }, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def bug_mark_resolved(
    bug_id: Annotated[int, Field(description="The ID of the bug to mark as resolved", ge=1)]
) -> str:
    """Mark a bug as resolved after all its fix features pass.

    This tool checks if all features with parent_bug_id matching the bug_id
    have passes=true. If so, it marks the bug as resolved.

    Call this after completing the last fix feature for a bug.

    Args:
        bug_id: The ID of the bug to mark as resolved

    Returns:
        JSON with success status or error if fixes are incomplete
    """
    session = get_session()
    try:
        bug = session.query(Feature).filter(Feature.id == bug_id).first()

        if bug is None:
            return json.dumps({"error": f"Bug with ID {bug_id} not found"})

        if bug.item_type != "bug":
            return json.dumps({"error": f"Item {bug_id} is not a bug (type: {bug.item_type})"})

        # Check all fix features for this bug
        fixes = session.query(Feature).filter(Feature.parent_bug_id == bug_id).all()

        if not fixes:
            return json.dumps({
                "error": f"No fix features found for bug {bug_id}. Create fixes using feature_create_bulk with parent_bug_id."
            })

        pending_fixes = [f.id for f in fixes if not f.passes]

        if pending_fixes:
            return json.dumps({
                "error": f"Bug cannot be resolved. Pending fix features: {pending_fixes}",
                "pending_count": len(pending_fixes),
                "total_fixes": len(fixes)
            })

        # All fixes pass - resolve the bug
        bug.bug_status = "resolved"
        bug.passes = True
        bug.in_progress = False
        session.commit()
        session.refresh(bug)

        return json.dumps({
            "success": True,
            "bug_id": bug_id,
            "bug_name": bug.name,
            "fixes_completed": len(fixes),
            "message": f"Bug '{bug.name}' resolved with {len(fixes)} fix(es)"
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def bug_get_status(
    bug_id: Annotated[int, Field(description="The ID of the bug to check", ge=1)]
) -> str:
    """Get the current status of a bug and its fix features.

    Args:
        bug_id: The ID of the bug to check

    Returns:
        JSON with bug details and fix feature statuses
    """
    session = get_session()
    try:
        bug = session.query(Feature).filter(Feature.id == bug_id).first()

        if bug is None:
            return json.dumps({"error": f"Bug with ID {bug_id} not found"})

        if bug.item_type != "bug":
            return json.dumps({"error": f"Item {bug_id} is not a bug (type: {bug.item_type})"})

        # Get all fix features
        fixes = session.query(Feature).filter(Feature.parent_bug_id == bug_id).all()

        fix_details = []
        passing_count = 0
        for f in fixes:
            fix_details.append({
                "id": f.id,
                "name": f.name,
                "passes": f.passes,
                "in_progress": f.in_progress
            })
            if f.passes:
                passing_count += 1

        return json.dumps({
            "bug": bug.to_dict(),
            "status": bug.bug_status,
            "fixes": fix_details,
            "fixes_total": len(fixes),
            "fixes_passing": passing_count,
            "can_resolve": len(fixes) > 0 and passing_count == len(fixes)
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def project_completion_check() -> str:
    """Check if all features are complete and generate completion report.

    This tool checks if 100% of features are passing. If so, it:
    1. Generates COMPLETION_REPORT.md with full project summary
    2. Collects statistics (features, categories, layers, git commits, LOC)
    3. Sends completion webhook if configured (PROGRESS_N8N_WEBHOOK_URL)

    Call this after marking the final feature as passing to trigger
    the completion workflow and generate documentation.

    Returns:
        JSON with:
        - completed (bool): True if all features pass
        - remaining (int): Number of features still pending
        - report_path (str): Path to generated report (if completed)
        - stats (dict): Completion statistics (if completed)
    """
    result = check_project_completion(PROJECT_DIR)

    response = {
        "completed": result.is_complete,
        "remaining": result.remaining,
    }

    if result.is_complete and result.stats:
        response["report_path"] = str(result.report_path) if result.report_path else None
        response["stats"] = {
            "total_features": result.stats.total_features,
            "completion_date": result.stats.completion_date.isoformat(),
            "git_commits": result.stats.git_commits,
            "lines_of_code": result.stats.lines_of_code,
            "categories": result.stats.categories,
            "layers": result.stats.layers,
        }
        response["message"] = (
            f"Project completed! {result.stats.total_features} features implemented. "
            f"Report generated at {result.report_path}"
        )

        # Send webhook notification
        reporter = CompletionReporter(PROJECT_DIR)
        webhook_sent = reporter.send_completion_webhook(result.stats)
        response["webhook_sent"] = webhook_sent
    else:
        response["message"] = f"{result.remaining} features remaining. Keep implementing!"

    return json.dumps(response, indent=2)


@mcp.tool()
def feature_export_markdown() -> str:
    """Export all features to markdown format for documentation.

    Generates a markdown document listing all features grouped by category,
    showing their status (passing/pending), description, and steps.

    Use this for:
    - Creating documentation
    - Reviewing project scope
    - Sharing feature list with stakeholders

    Returns:
        Markdown-formatted string with all features
    """
    reporter = CompletionReporter(PROJECT_DIR)
    markdown = reporter.export_features_to_markdown()
    return markdown


@mcp.tool()
def feature_get_skills_context(
    feature_id: Annotated[int, Field(description="The ID of the feature to get skills for", ge=1)]
) -> str:
    """Get expert skills context for a feature based on its assigned_skills.

    When a feature has assigned_skills from the Skills Analysis system,
    this tool loads the skill content from the .claude/skills/ directory
    and returns it as context for implementation.

    Use this after feature_get_next if the feature has assigned_skills.
    The returned context contains best practices and guidelines from the
    assigned skills to guide your implementation.

    Args:
        feature_id: The ID of the feature to get skills for

    Returns:
        JSON with:
        - has_skills (bool): True if feature has assigned skills
        - skills_context (str): Combined skills content for implementation
        - skill_names (list[str]): Names of the assigned skills
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        assigned_skills = getattr(feature, 'assigned_skills', None)

        if not assigned_skills or len(assigned_skills) == 0:
            return json.dumps({
                "has_skills": False,
                "skills_context": "",
                "skill_names": [],
                "message": "No skills assigned to this feature"
            })

        # Get the harness directory (where skills are stored)
        harness_dir = Path(__file__).parent.parent
        skills_dir = harness_dir / ".claude" / "skills"

        if not skills_dir.exists():
            return json.dumps({
                "error": f"Skills directory not found: {skills_dir}",
                "has_skills": False
            })

        # Load skills content
        skills_parts = []
        loaded_skills = []

        for skill_name in assigned_skills:
            skill_md_path = skills_dir / skill_name / "SKILL.md"

            if skill_md_path.exists():
                try:
                    content = skill_md_path.read_text(encoding="utf-8")
                    # Truncate very long skill content
                    if len(content) > 4000:
                        content = content[:4000] + "\n\n[... truncated for brevity ...]"

                    skills_parts.append(f"### {skill_name}\n\n{content}")
                    loaded_skills.append(skill_name)
                except (OSError, PermissionError) as e:
                    print(f"Warning: Could not load skill {skill_name}: {e}")
                    continue

        if not skills_parts:
            return json.dumps({
                "has_skills": True,
                "skills_context": "",
                "skill_names": assigned_skills,
                "loaded_skills": [],
                "message": "Skills assigned but content could not be loaded"
            })

        skills_context = (
            "## Expert Skills for This Feature\n\n"
            "Apply these best practices and patterns:\n\n"
            + "\n\n---\n\n".join(skills_parts)
        )

        return json.dumps({
            "has_skills": True,
            "skills_context": skills_context,
            "skill_names": assigned_skills,
            "loaded_skills": loaded_skills,
            "message": f"Loaded {len(loaded_skills)} skill(s) for implementation guidance"
        }, indent=2)
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
