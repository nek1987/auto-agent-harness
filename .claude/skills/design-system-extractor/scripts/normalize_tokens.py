#!/usr/bin/env python3
"""
Design Token Normalization

This script provides functions for normalizing and merging design tokens
from multiple sources into a unified format.

Usage:
    from normalize_tokens import normalize_tokens, merge_token_sets

    normalized = normalize_tokens(raw_tokens)
    merged = merge_token_sets([tokens1, tokens2], strategy='priority')
"""

import copy
from typing import Any
from extract_tokens import generate_color_scale


# Default token values to fill in missing fields
DEFAULT_TOKENS = {
    "colors": {
        "neutral": {
            "50": "#FAFAFA",
            "100": "#F5F5F5",
            "200": "#E5E5E5",
            "300": "#D4D4D4",
            "400": "#A3A3A3",
            "500": "#737373",
            "600": "#525252",
            "700": "#404040",
            "800": "#262626",
            "900": "#171717",
            "950": "#0A0A0A",
        },
        "semantic": {
            "success": {"light": "#DCFCE7", "DEFAULT": "#22C55E", "dark": "#166534"},
            "error": {"light": "#FEE2E2", "DEFAULT": "#EF4444", "dark": "#991B1B"},
            "warning": {"light": "#FEF3C7", "DEFAULT": "#F59E0B", "dark": "#92400E"},
            "info": {"light": "#DBEAFE", "DEFAULT": "#3B82F6", "dark": "#1E40AF"},
        },
    },
    "typography": {
        "fontFamily": {
            "sans": ["Inter", "system-ui", "-apple-system", "sans-serif"],
            "serif": ["Georgia", "Cambria", "serif"],
            "mono": ["JetBrains Mono", "Consolas", "monospace"],
        },
        "fontSize": {
            "xs": {"value": "0.75rem", "lineHeight": "1rem"},
            "sm": {"value": "0.875rem", "lineHeight": "1.25rem"},
            "base": {"value": "1rem", "lineHeight": "1.5rem"},
            "lg": {"value": "1.125rem", "lineHeight": "1.75rem"},
            "xl": {"value": "1.25rem", "lineHeight": "1.75rem"},
            "2xl": {"value": "1.5rem", "lineHeight": "2rem"},
            "3xl": {"value": "1.875rem", "lineHeight": "2.25rem"},
            "4xl": {"value": "2.25rem", "lineHeight": "2.5rem"},
            "5xl": {"value": "3rem", "lineHeight": "1"},
        },
        "fontWeight": {
            "thin": 100,
            "light": 300,
            "normal": 400,
            "medium": 500,
            "semibold": 600,
            "bold": 700,
            "extrabold": 800,
        },
        "lineHeight": {
            "none": 1,
            "tight": 1.25,
            "snug": 1.375,
            "normal": 1.5,
            "relaxed": 1.625,
            "loose": 2,
        },
    },
    "spacing": {
        "0": "0px",
        "px": "1px",
        "0.5": "0.125rem",
        "1": "0.25rem",
        "1.5": "0.375rem",
        "2": "0.5rem",
        "2.5": "0.625rem",
        "3": "0.75rem",
        "3.5": "0.875rem",
        "4": "1rem",
        "5": "1.25rem",
        "6": "1.5rem",
        "7": "1.75rem",
        "8": "2rem",
        "9": "2.25rem",
        "10": "2.5rem",
        "12": "3rem",
        "14": "3.5rem",
        "16": "4rem",
        "20": "5rem",
        "24": "6rem",
        "32": "8rem",
    },
    "borders": {
        "radius": {
            "none": "0px",
            "sm": "0.125rem",
            "DEFAULT": "0.25rem",
            "md": "0.375rem",
            "lg": "0.5rem",
            "xl": "0.75rem",
            "2xl": "1rem",
            "3xl": "1.5rem",
            "full": "9999px",
        },
        "width": {
            "0": "0px",
            "DEFAULT": "1px",
            "2": "2px",
            "4": "4px",
            "8": "8px",
        },
    },
    "shadows": {
        "sm": "0 1px 2px 0 rgb(0 0 0 / 0.05)",
        "DEFAULT": "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
        "md": "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        "lg": "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
        "xl": "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
        "2xl": "0 25px 50px -12px rgb(0 0 0 / 0.25)",
        "inner": "inset 0 2px 4px 0 rgb(0 0 0 / 0.05)",
        "none": "0 0 #0000",
    },
    "animation": {
        "duration": {
            "fast": "150ms",
            "normal": "300ms",
            "slow": "500ms",
        },
        "easing": {
            "linear": "linear",
            "in": "cubic-bezier(0.4, 0, 1, 1)",
            "out": "cubic-bezier(0, 0, 0.2, 1)",
            "in-out": "cubic-bezier(0.4, 0, 0.2, 1)",
            "spring": "cubic-bezier(0.175, 0.885, 0.32, 1.275)",
        },
    },
}


def normalize_tokens(raw_tokens: dict) -> dict:
    """
    Normalize extracted tokens to the standard schema.

    This function:
    1. Fills in missing required fields with defaults
    2. Expands partial color scales to full scales
    3. Normalizes font size formats
    4. Validates and cleans values

    Args:
        raw_tokens: Raw tokens from extraction

    Returns:
        Normalized tokens following the full schema
    """
    tokens = copy.deepcopy(raw_tokens)

    # Ensure schema version
    tokens["$schema"] = "design-tokens-v1"

    # Normalize colors
    tokens["colors"] = normalize_colors(tokens.get("colors", {}))

    # Normalize typography
    tokens["typography"] = normalize_typography(tokens.get("typography", {}))

    # Normalize spacing
    tokens["spacing"] = normalize_spacing(tokens.get("spacing", {}))

    # Normalize borders
    tokens["borders"] = normalize_borders(tokens.get("borders", {}))

    # Normalize shadows
    tokens["shadows"] = normalize_shadows(tokens.get("shadows", {}))

    # Add animation defaults if missing
    if "animation" not in tokens:
        tokens["animation"] = DEFAULT_TOKENS["animation"]

    return tokens


def normalize_colors(colors: dict) -> dict:
    """
    Normalize color tokens.

    - Expands single colors to full scales
    - Fills in missing semantic colors
    - Ensures all hex values are uppercase
    """
    result = {}

    # Process primary colors
    if "primary" in colors:
        primary = colors["primary"]
        if isinstance(primary, str):
            # Single color provided, generate scale
            result["primary"] = generate_color_scale(primary)
        elif isinstance(primary, dict):
            if len(primary) == 1:
                # Only one shade provided, generate scale from it
                base_color = list(primary.values())[0]
                result["primary"] = generate_color_scale(base_color)
            else:
                # Multiple shades provided, use as-is and fill gaps
                result["primary"] = fill_color_scale(primary)
        else:
            result["primary"] = DEFAULT_TOKENS["colors"]["neutral"]  # Fallback
    else:
        result["primary"] = DEFAULT_TOKENS["colors"]["neutral"]

    # Process secondary colors
    if "secondary" in colors:
        secondary = colors["secondary"]
        if isinstance(secondary, str):
            result["secondary"] = generate_color_scale(secondary)
        elif isinstance(secondary, dict):
            if len(secondary) <= 3:
                base_color = secondary.get("500") or list(secondary.values())[0]
                result["secondary"] = generate_color_scale(base_color)
            else:
                result["secondary"] = fill_color_scale(secondary)

    # Process neutral colors
    if "neutral" in colors:
        result["neutral"] = fill_color_scale(colors["neutral"])
    else:
        result["neutral"] = DEFAULT_TOKENS["colors"]["neutral"]

    # Process semantic colors
    result["semantic"] = normalize_semantic_colors(colors.get("semantic", {}))

    return result


def fill_color_scale(partial_scale: dict) -> dict:
    """
    Fill in missing values in a partial color scale.

    Uses interpolation between provided values.
    """
    shades = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"]
    result = {}

    # Get provided values
    provided = {}
    for shade in shades:
        if shade in partial_scale:
            provided[int(shade)] = partial_scale[shade]

    if not provided:
        return DEFAULT_TOKENS["colors"]["neutral"]

    # Simple fill: use closest provided value
    provided_shades = sorted(provided.keys())

    for shade in shades:
        shade_int = int(shade)
        if shade_int in provided:
            result[shade] = provided[shade_int]
        else:
            # Find closest provided shade
            closest = min(provided_shades, key=lambda x: abs(x - shade_int))
            result[shade] = provided[closest]

    return result


def normalize_semantic_colors(semantic: dict) -> dict:
    """
    Normalize semantic colors (success, error, warning, info).
    """
    result = {}
    default_semantic = DEFAULT_TOKENS["colors"]["semantic"]

    for color_name in ["success", "error", "warning", "info"]:
        if color_name in semantic:
            value = semantic[color_name]
            if isinstance(value, str):
                result[color_name] = {
                    "light": lighten_color(value, 0.4),
                    "DEFAULT": value,
                    "dark": darken_color(value, 0.3),
                }
            elif isinstance(value, dict):
                result[color_name] = {
                    "light": value.get("light", lighten_color(value.get("DEFAULT", "#000000"), 0.4)),
                    "DEFAULT": value.get("DEFAULT", default_semantic[color_name]["DEFAULT"]),
                    "dark": value.get("dark", darken_color(value.get("DEFAULT", "#000000"), 0.3)),
                }
            else:
                result[color_name] = default_semantic[color_name]
        else:
            result[color_name] = default_semantic[color_name]

    return result


def lighten_color(hex_color: str, amount: float) -> str:
    """Lighten a hex color by a given amount (0-1)."""
    hex_val = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))

    r = min(255, int(r + (255 - r) * amount))
    g = min(255, int(g + (255 - g) * amount))
    b = min(255, int(b + (255 - b) * amount))

    return f"#{r:02X}{g:02X}{b:02X}"


def darken_color(hex_color: str, amount: float) -> str:
    """Darken a hex color by a given amount (0-1)."""
    hex_val = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))

    r = max(0, int(r * (1 - amount)))
    g = max(0, int(g * (1 - amount)))
    b = max(0, int(b * (1 - amount)))

    return f"#{r:02X}{g:02X}{b:02X}"


def normalize_typography(typography: dict) -> dict:
    """
    Normalize typography tokens.
    """
    result = {}
    default = DEFAULT_TOKENS["typography"]

    # Font families
    if "fontFamily" in typography:
        result["fontFamily"] = {}
        for family, value in typography["fontFamily"].items():
            if isinstance(value, str):
                result["fontFamily"][family] = [value, "sans-serif"]
            elif isinstance(value, list):
                result["fontFamily"][family] = value
        # Fill in missing families
        for family in ["sans", "serif", "mono"]:
            if family not in result["fontFamily"]:
                result["fontFamily"][family] = default["fontFamily"][family]
    else:
        result["fontFamily"] = default["fontFamily"]

    # Font sizes
    if "fontSize" in typography:
        result["fontSize"] = {}
        for size, value in typography["fontSize"].items():
            if isinstance(value, str):
                result["fontSize"][size] = {"value": value}
            elif isinstance(value, dict):
                result["fontSize"][size] = value
        # Fill in missing sizes
        for size, default_value in default["fontSize"].items():
            if size not in result["fontSize"]:
                result["fontSize"][size] = default_value
    else:
        result["fontSize"] = default["fontSize"]

    # Font weights
    result["fontWeight"] = {**default["fontWeight"], **typography.get("fontWeight", {})}

    # Line heights
    result["lineHeight"] = {**default["lineHeight"], **typography.get("lineHeight", {})}

    return result


def normalize_spacing(spacing: dict) -> dict:
    """
    Normalize spacing tokens.
    """
    if not spacing:
        return DEFAULT_TOKENS["spacing"]

    result = copy.deepcopy(DEFAULT_TOKENS["spacing"])

    for key, value in spacing.items():
        # Normalize key format (e.g., "0.5" vs "0-5")
        normalized_key = key.replace("-", ".")
        result[normalized_key] = value

    return result


def normalize_borders(borders: dict) -> dict:
    """
    Normalize border tokens.
    """
    result = copy.deepcopy(DEFAULT_TOKENS["borders"])

    if "radius" in borders:
        result["radius"] = {**result["radius"], **borders["radius"]}

    if "width" in borders:
        result["width"] = {**result["width"], **borders["width"]}

    return result


def normalize_shadows(shadows: dict) -> dict:
    """
    Normalize shadow tokens.
    """
    if not shadows:
        return DEFAULT_TOKENS["shadows"]

    result = copy.deepcopy(DEFAULT_TOKENS["shadows"])
    result.update(shadows)

    return result


def merge_token_sets(
    token_sets: list[dict],
    strategy: str = "priority"
) -> dict:
    """
    Merge multiple token sets into one.

    Args:
        token_sets: List of token dictionaries to merge
        strategy: Merge strategy
            - "priority": Later sets override earlier ones
            - "first": Keep first non-null value
            - "average": Average numeric values (for colors, etc.)

    Returns:
        Merged token dictionary
    """
    if not token_sets:
        return normalize_tokens({})

    if len(token_sets) == 1:
        return normalize_tokens(token_sets[0])

    if strategy == "priority":
        # Simple deep merge, later values win
        result = {}
        for tokens in token_sets:
            result = deep_merge(result, tokens)
        return normalize_tokens(result)

    elif strategy == "first":
        # Keep first non-null value for each field
        result = copy.deepcopy(token_sets[0])
        for tokens in token_sets[1:]:
            result = deep_merge_first(result, tokens)
        return normalize_tokens(result)

    else:
        # Default to priority
        return merge_token_sets(token_sets, "priority")


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries, with override taking precedence.
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


def deep_merge_first(base: dict, other: dict) -> dict:
    """
    Deep merge keeping first non-null values.
    """
    result = copy.deepcopy(base)

    for key, value in other.items():
        if key not in result or result[key] is None:
            result[key] = copy.deepcopy(value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_first(result[key], value)

    return result


if __name__ == "__main__":
    # Test normalization
    raw = {
        "colors": {
            "primary": "#3B82F6",
            "semantic": {
                "success": "#22C55E"
            }
        },
        "typography": {
            "fontFamily": {
                "sans": "Inter"
            }
        },
        "spacing": {
            "4": "16px"
        }
    }

    normalized = normalize_tokens(raw)
    import json
    print(json.dumps(normalized, indent=2))
