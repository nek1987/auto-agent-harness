#!/usr/bin/env python3
"""
MCP Server for Component Reference Operations
==============================================

Provides tools for the autonomous agent to analyze code components from external
sources (e.g., v0.dev, shadcn/ui) and use them as references for generating
new components adapted to the project's architecture.

Unlike Redesign MCP which works with visual references (images/URLs),
this works with actual code files to extract patterns and structures.

Tools:
- component_ref_get_status: Get current session status
- component_ref_start_session: Initialize a new session
- component_ref_add_components: Add component files from ZIP
- component_ref_analyze: Analyze components with Claude
- component_ref_get_analysis: Get analysis results
- component_ref_generate_plan: Generate component creation plan
- component_ref_get_plan: Get the generation plan
- component_ref_apply_to_feature: Link reference to a feature
- component_ref_complete: Mark session as complete
"""

import json
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import ComponentReferenceSession, Feature, create_database

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()

# Global database session maker (initialized on startup)
_session_maker = None
_engine = None
_anthropic_client = None


def get_anthropic_client():
    """Lazy-load Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        try:
            from anthropic import Anthropic
            _anthropic_client = Anthropic()
        except ImportError:
            raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic")
    return _anthropic_client


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize database on startup, cleanup on shutdown."""
    global _session_maker, _engine

    # Initialize database
    _engine, _session_maker = create_database(PROJECT_DIR)

    yield

    # Cleanup
    if _engine:
        _engine.dispose()


# Initialize the MCP server
mcp = FastMCP("component_ref", lifespan=server_lifespan)


def get_session():
    """Get a new database session."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized")
    return _session_maker()


def get_active_session_sync(project_name: str) -> Optional[ComponentReferenceSession]:
    """Get the active component reference session for a project (synchronous)."""
    session = get_session()
    try:
        return (
            session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "complete",
                ComponentReferenceSession.status != "failed",
            )
            .order_by(ComponentReferenceSession.created_at.desc())
            .first()
        )
    finally:
        session.close()


# Analysis prompt for Claude
COMPONENT_ANALYSIS_PROMPT = """Analyze this component code as a reference for creating similar components.

Component: {filename}
Framework: {framework}

```{language}
{code}
```

Extract and return as JSON:

{{
  "component_name": "Name of the component",
  "purpose": "What this component does (1-2 sentences)",

  "structure": {{
    "composition_pattern": "How it's composed (atomic, compound, container, page, etc.)",
    "children_handling": "How it handles children/slots",
    "layout_approach": "flex, grid, absolute, etc."
  }},

  "props_interface": {{
    "required_props": ["prop1", "prop2"],
    "optional_props": ["prop3"],
    "prop_patterns": ["render props", "compound components", "controlled/uncontrolled", etc.]
  }},

  "styling": {{
    "approach": "tailwind | css-modules | styled-components | inline | scss",
    "key_classes": ["bg-white", "rounded-lg", "shadow-md"],
    "responsive_patterns": ["mobile-first", "breakpoints used"],
    "color_tokens": ["primary", "secondary", "neutral"],
    "spacing_tokens": ["p-4", "gap-2", "m-auto"]
  }},

  "state_and_logic": {{
    "hooks_used": ["useState", "useEffect", "custom hooks"],
    "state_pattern": "local | context | external | none",
    "side_effects": ["API calls", "subscriptions", "none"]
  }},

  "accessibility": {{
    "aria_attributes": ["aria-label", "role"],
    "keyboard_support": true/false,
    "focus_management": "description or none"
  }},

  "dependencies": {{
    "icons": ["lucide-react", "heroicons", "none"],
    "animations": ["framer-motion", "tailwind-animate", "none"],
    "utilities": ["clsx", "tailwind-merge", "none"]
  }},

  "reusability_tips": [
    "How to adapt this pattern",
    "What to customize",
    "Common variations"
  ]
}}

Focus on extracting PATTERNS that can be applied to create SIMILAR (not identical) components.
Return ONLY valid JSON."""


@mcp.tool()
def component_ref_get_status() -> str:
    """Get the status of the active component reference session.

    Returns the current session with its status, components count,
    analysis preview, and generation plan overview.

    Use this at the start of a component reference task to understand the current state.

    Returns:
        JSON with session details or message if no active session.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "complete",
                ComponentReferenceSession.status != "failed",
            )
            .order_by(ComponentReferenceSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "has_session": False,
                "message": "No active component reference session. Use component_ref_start_session to begin."
            })

        # Build response
        response = {
            "has_session": True,
            "session_id": session.id,
            "status": session.status,
            "source_type": session.source_type,
            "source_url": session.source_url,
            "components_count": len(session.components or []),
            "has_analysis": session.extracted_analysis is not None,
            "has_plan": session.generation_plan is not None,
            "target_framework": session.target_framework,
        }

        # Add analysis preview if available
        if session.extracted_analysis:
            analysis = session.extracted_analysis
            response["analysis_preview"] = {
                "components_analyzed": len(analysis.get("components", [])),
                "patterns_found": len(analysis.get("common_patterns", [])),
                "styling_approach": analysis.get("styling_approach"),
                "dependencies": analysis.get("dependencies", []),
            }

        # Add plan overview if available
        if session.generation_plan:
            plan = session.generation_plan
            response["plan_overview"] = {
                "target_framework": plan.get("target_framework"),
                "components_to_create": len(plan.get("components_to_create", [])),
            }

        if session.error_message:
            response["error_message"] = session.error_message

        return json.dumps(response, indent=2)
    finally:
        db_session.close()


@mcp.tool()
def component_ref_start_session(
    source_type: Annotated[str, Field(description="Source type: 'v0', 'shadcn', or 'custom'")] = "custom",
    source_url: Annotated[str, Field(description="Original URL if available (e.g., v0.dev link)")] = "",
) -> str:
    """Start a new component reference session for the current project.

    Creates a new session in 'uploading' status, ready to receive
    component files. If an active session exists, returns it.

    Args:
        source_type: Source of components ('v0', 'shadcn', 'custom')
        source_url: Original URL if available

    Returns:
        JSON with the session details.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        # Check for existing active session
        existing = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "complete",
                ComponentReferenceSession.status != "failed",
            )
            .first()
        )

        if existing:
            return json.dumps({
                "action": "resumed",
                "session_id": existing.id,
                "status": existing.status,
                "message": f"Resumed existing session {existing.id} in status '{existing.status}'"
            })

        # Create new session
        session = ComponentReferenceSession(
            project_name=project_name,
            status="uploading",
            source_type=source_type,
            source_url=source_url if source_url else None,
            components=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        return json.dumps({
            "action": "created",
            "session_id": session.id,
            "status": session.status,
            "source_type": source_type,
            "message": "New component reference session created. Add components using component_ref_add_components."
        }, indent=2)
    finally:
        db_session.close()


@mcp.tool()
def component_ref_add_components(
    components: Annotated[str, Field(description="JSON array of components: [{filename, content, framework}]")],
) -> str:
    """Add component files to the active session.

    Use this to add component code extracted from a ZIP file or other source.
    Each component should have filename, content, and detected framework.

    Args:
        components: JSON string with array of component objects

    Returns:
        JSON with updated component count.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status == "uploading",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session in 'uploading' status. Start a new session first."
            })

        # Parse components JSON
        try:
            new_components = json.loads(components)
            if not isinstance(new_components, list):
                return json.dumps({
                    "error": "Components must be a JSON array."
                })
        except json.JSONDecodeError as e:
            return json.dumps({
                "error": f"Invalid JSON: {str(e)}"
            })

        # Add components
        existing_components = session.components or []
        for comp in new_components:
            if not isinstance(comp, dict):
                continue
            if "filename" not in comp or "content" not in comp:
                continue

            # Detect framework if not provided
            framework = comp.get("framework", _detect_component_framework(comp["filename"], comp["content"]))

            existing_components.append({
                "filename": comp["filename"],
                "content": comp["content"],
                "framework": framework,
                "file_type": _detect_file_type(comp["filename"]),
                "added_at": datetime.utcnow().isoformat(),
            })

        session.components = existing_components
        session.updated_at = datetime.utcnow()
        db_session.commit()

        return json.dumps({
            "success": True,
            "components_count": len(existing_components),
            "added": len(new_components),
            "message": f"Added {len(new_components)} component(s). Total: {len(existing_components)}"
        })
    finally:
        db_session.close()


def _detect_component_framework(filename: str, content: str) -> str:
    """Detect the framework used by a component."""
    filename_lower = filename.lower()

    # Check file extension
    if filename_lower.endswith(".vue"):
        return "vue"
    if filename_lower.endswith(".svelte"):
        return "svelte"

    # Check content patterns
    if "import React" in content or "from 'react'" in content or 'from "react"' in content:
        if "tailwind" in content.lower() or "className=" in content:
            return "react-tailwind"
        return "react"

    if "<template>" in content and "<script" in content:
        return "vue"

    if "import { Component }" in content or "@Component" in content:
        return "angular"

    # Default based on extension
    if filename_lower.endswith((".tsx", ".jsx")):
        return "react"

    return "unknown"


def _detect_file_type(filename: str) -> str:
    """Detect the type of file."""
    filename_lower = filename.lower()

    if filename_lower.endswith((".tsx", ".jsx")):
        return "component"
    if filename_lower.endswith(".vue"):
        return "component"
    if filename_lower.endswith((".css", ".scss", ".sass")):
        return "styles"
    if filename_lower.endswith(".ts"):
        if "hook" in filename_lower or filename_lower.startswith("use"):
            return "hook"
        if "util" in filename_lower or "helper" in filename_lower:
            return "utility"
        return "typescript"
    if filename_lower.endswith(".js"):
        return "javascript"

    return "other"


@mcp.tool()
def component_ref_analyze() -> str:
    """Analyze all components in the active session using Claude.

    Uses Claude to analyze each component and extract:
    - Composition patterns
    - Props interface patterns
    - Styling approach and tokens
    - State management patterns
    - Accessibility patterns
    - Dependencies

    Must have at least one component added before calling this.

    Returns:
        JSON with analysis results or error.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status == "uploading",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session in 'uploading' status."
            })

        if not session.components or len(session.components) == 0:
            return json.dumps({
                "error": "No components added. Add at least one component before analyzing."
            })

        # Update status
        session.status = "analyzing"
        db_session.commit()

        try:
            # Analyze each component
            client = get_anthropic_client()
            component_analyses = []

            for comp in session.components:
                if comp.get("file_type") not in ("component", "hook"):
                    continue

                analysis = _analyze_single_component(
                    client,
                    comp["filename"],
                    comp["content"],
                    comp["framework"]
                )
                component_analyses.append({
                    "filename": comp["filename"],
                    "framework": comp["framework"],
                    "analysis": analysis,
                })

            # Extract common patterns
            common_patterns = _extract_common_patterns(component_analyses)

            # Build full analysis
            full_analysis = {
                "components": component_analyses,
                "common_patterns": common_patterns,
                "styling_approach": _detect_styling_approach(component_analyses),
                "dependencies": _collect_dependencies(component_analyses),
                "analyzed_at": datetime.utcnow().isoformat(),
            }

            # Detect target framework
            from lib.framework_detector import detect_framework
            framework_info = detect_framework(PROJECT_DIR)
            session.target_framework = framework_info.identifier

            # Update session
            session.extracted_analysis = full_analysis
            session.status = "planning"
            session.updated_at = datetime.utcnow()
            db_session.commit()

            return json.dumps({
                "success": True,
                "components_analyzed": len(component_analyses),
                "common_patterns": common_patterns,
                "styling_approach": full_analysis["styling_approach"],
                "target_framework": session.target_framework,
                "message": "Analysis complete. Use component_ref_generate_plan to create generation plan."
            }, indent=2)

        except Exception as e:
            session.status = "failed"
            session.error_message = str(e)
            db_session.commit()
            return json.dumps({
                "error": f"Analysis failed: {str(e)}"
            })

    finally:
        db_session.close()


def _analyze_single_component(client, filename: str, content: str, framework: str) -> dict:
    """Analyze a single component using Claude."""
    # Determine language for code block
    language = "tsx" if filename.endswith((".tsx", ".jsx")) else "vue" if filename.endswith(".vue") else "typescript"

    prompt = COMPONENT_ANALYSIS_PROMPT.format(
        filename=filename,
        framework=framework,
        language=language,
        code=content[:10000]  # Limit content size
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    # Parse JSON from response
    response_text = message.content[0].text

    # Try to find JSON in response
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Return basic structure if parsing fails
    return {
        "component_name": filename,
        "purpose": "Could not parse analysis",
        "raw_response": response_text[:500],
    }


def _extract_common_patterns(analyses: list[dict]) -> list[dict]:
    """Extract common patterns from multiple component analyses."""
    patterns = []
    seen_patterns = set()

    for comp in analyses:
        analysis = comp.get("analysis", {})

        # Collect composition patterns
        structure = analysis.get("structure", {})
        if structure.get("composition_pattern") and structure["composition_pattern"] not in seen_patterns:
            seen_patterns.add(structure["composition_pattern"])
            patterns.append({
                "type": "composition",
                "name": structure["composition_pattern"],
                "description": f"Component composition pattern from {comp['filename']}",
            })

        # Collect prop patterns
        props = analysis.get("props_interface", {})
        for pattern in props.get("prop_patterns", []):
            if pattern not in seen_patterns:
                seen_patterns.add(pattern)
                patterns.append({
                    "type": "props",
                    "name": pattern,
                    "description": f"Props pattern from {comp['filename']}",
                })

    return patterns


def _detect_styling_approach(analyses: list[dict]) -> str:
    """Detect the most common styling approach."""
    approaches = {}

    for comp in analyses:
        analysis = comp.get("analysis", {})
        styling = analysis.get("styling", {})
        approach = styling.get("approach", "unknown")
        approaches[approach] = approaches.get(approach, 0) + 1

    if not approaches:
        return "unknown"

    return max(approaches, key=approaches.get)


def _collect_dependencies(analyses: list[dict]) -> list[str]:
    """Collect all unique dependencies from analyses."""
    deps = set()

    for comp in analyses:
        analysis = comp.get("analysis", {})
        dependencies = analysis.get("dependencies", {})

        for category, items in dependencies.items():
            if isinstance(items, list):
                for item in items:
                    if item and item != "none":
                        deps.add(item)

    return sorted(list(deps))


@mcp.tool()
def component_ref_get_analysis() -> str:
    """Get the extracted analysis from the active session.

    Returns the full analysis structure for use in implementation.

    Returns:
        JSON with the component analysis.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "failed",
            )
            .order_by(ComponentReferenceSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session."
            })

        if not session.extracted_analysis:
            return json.dumps({
                "error": "No analysis extracted yet. Run component_ref_analyze first."
            })

        return json.dumps({
            "analysis": session.extracted_analysis,
            "target_framework": session.target_framework,
            "source_type": session.source_type,
        }, indent=2)

    finally:
        db_session.close()


@mcp.tool()
def component_ref_generate_plan(
    target_components: Annotated[str, Field(description="JSON array of component names to create, e.g., ['Button', 'Card']")],
    adaptation_notes: Annotated[str, Field(description="Notes on how to adapt components for this project")] = "",
) -> str:
    """Generate a plan for creating new components based on the analysis.

    Creates a plan that maps reference components to new components
    adapted to the target project's architecture and design system.

    Args:
        target_components: JSON array of component names to create
        adaptation_notes: Notes on specific adaptations needed

    Returns:
        JSON with the generation plan.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status == "planning",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session in 'planning' status. Run analyze first."
            })

        if not session.extracted_analysis:
            return json.dumps({
                "error": "No analysis available. Run component_ref_analyze first."
            })

        # Parse target components
        try:
            components_to_create = json.loads(target_components)
            if not isinstance(components_to_create, list):
                return json.dumps({
                    "error": "target_components must be a JSON array."
                })
        except json.JSONDecodeError as e:
            return json.dumps({
                "error": f"Invalid JSON for target_components: {str(e)}"
            })

        try:
            analysis = session.extracted_analysis

            # Build generation plan
            plan_components = []
            for comp_name in components_to_create:
                # Find matching reference component
                reference = None
                for comp in analysis.get("components", []):
                    comp_analysis = comp.get("analysis", {})
                    if comp_analysis.get("component_name", "").lower() == comp_name.lower():
                        reference = comp
                        break

                plan_components.append({
                    "name": comp_name,
                    "based_on": reference["filename"] if reference else None,
                    "patterns_to_apply": analysis.get("common_patterns", []),
                    "styling_approach": analysis.get("styling_approach"),
                    "adaptations": adaptation_notes,
                })

            plan = {
                "target_framework": session.target_framework,
                "components_to_create": plan_components,
                "dependencies_needed": analysis.get("dependencies", []),
                "styling_approach": analysis.get("styling_approach"),
                "created_at": datetime.utcnow().isoformat(),
            }

            session.generation_plan = plan
            session.status = "generating"
            session.updated_at = datetime.utcnow()
            db_session.commit()

            return json.dumps({
                "success": True,
                "plan": plan,
                "message": "Generation plan created. Components are ready to be created based on the reference analysis."
            }, indent=2)

        except Exception as e:
            session.status = "failed"
            session.error_message = str(e)
            db_session.commit()
            return json.dumps({
                "error": f"Plan generation failed: {str(e)}"
            })

    finally:
        db_session.close()


@mcp.tool()
def component_ref_get_plan() -> str:
    """Get the generated plan from the active session.

    Returns the full plan structure with components to create.

    Returns:
        JSON with the generation plan.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "failed",
            )
            .order_by(ComponentReferenceSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session."
            })

        if not session.generation_plan:
            return json.dumps({
                "error": "No plan generated yet. Run component_ref_generate_plan first."
            })

        return json.dumps({
            "plan": session.generation_plan,
            "target_framework": session.target_framework,
            "status": session.status,
        }, indent=2)

    finally:
        db_session.close()


@mcp.tool()
def component_ref_apply_to_feature(
    feature_id: Annotated[int, Field(description="ID of the feature to link the reference to")],
) -> str:
    """Link the current component reference session to a feature.

    When a feature has a reference session linked, the coding agent
    will use the analysis as context when implementing the feature.

    Args:
        feature_id: The feature ID to link

    Returns:
        JSON with success status.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        # Get active session
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "failed",
            )
            .order_by(ComponentReferenceSession.created_at.desc())
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active component reference session."
            })

        # Get the feature
        feature = db_session.query(Feature).filter(Feature.id == feature_id).first()

        if not feature:
            return json.dumps({
                "error": f"Feature {feature_id} not found."
            })

        # Link the session to the feature
        feature.reference_session_id = session.id
        db_session.commit()

        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "feature_name": feature.name,
            "session_id": session.id,
            "message": f"Feature '{feature.name}' now linked to component reference session {session.id}."
        })

    finally:
        db_session.close()


@mcp.tool()
def component_ref_complete() -> str:
    """Mark the component reference session as complete.

    Call this after components have been created based on the reference.

    Returns:
        JSON with completion status.
    """
    project_name = PROJECT_DIR.name

    db_session = get_session()
    try:
        session = (
            db_session.query(ComponentReferenceSession)
            .filter(
                ComponentReferenceSession.project_name == project_name,
                ComponentReferenceSession.status != "complete",
                ComponentReferenceSession.status != "failed",
            )
            .first()
        )

        if not session:
            return json.dumps({
                "error": "No active session to complete."
            })

        session.status = "complete"
        session.updated_at = datetime.utcnow()
        db_session.commit()

        return json.dumps({
            "success": True,
            "session_id": session.id,
            "message": "Component reference session completed successfully!"
        })

    finally:
        db_session.close()


if __name__ == "__main__":
    mcp.run()
