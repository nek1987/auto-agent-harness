#!/usr/bin/env python3
"""
Design Token Output Generation

This script provides functions to convert normalized design tokens
into framework-specific output formats (Tailwind, CSS Variables, Shadcn).

Usage:
    from generate_output import (
        generate_tailwind_config,
        generate_css_variables,
        generate_shadcn_theme
    )

    tailwind_config = generate_tailwind_config(tokens)
    css_vars = generate_css_variables(tokens)
"""

import json
from typing import Any


def generate_tailwind_config(tokens: dict) -> str:
    """
    Generate tailwind.config.js content from design tokens.

    Args:
        tokens: Normalized design tokens dictionary

    Returns:
        String content for tailwind.config.js
    """
    config = {
        "content": [
            "./index.html",
            "./src/**/*.{js,ts,jsx,tsx,vue}",
        ],
        "theme": {
            "extend": {}
        },
        "plugins": []
    }

    extend = config["theme"]["extend"]

    # Colors
    if "colors" in tokens:
        extend["colors"] = {}
        for category, scale in tokens["colors"].items():
            if category == "semantic":
                # Flatten semantic colors
                for name, variants in scale.items():
                    if isinstance(variants, dict):
                        extend["colors"][name] = variants.get("DEFAULT", variants)
                    else:
                        extend["colors"][name] = variants
            else:
                extend["colors"][category] = scale

    # Font families
    if "typography" in tokens and "fontFamily" in tokens["typography"]:
        extend["fontFamily"] = {}
        for family, stack in tokens["typography"]["fontFamily"].items():
            if isinstance(stack, list):
                extend["fontFamily"][family] = stack
            else:
                extend["fontFamily"][family] = [stack]

    # Font sizes
    if "typography" in tokens and "fontSize" in tokens["typography"]:
        extend["fontSize"] = {}
        for size, value in tokens["typography"]["fontSize"].items():
            if isinstance(value, dict):
                extend["fontSize"][size] = [
                    value.get("value", "1rem"),
                    {"lineHeight": value.get("lineHeight", "1.5")}
                ]
            else:
                extend["fontSize"][size] = value

    # Border radius
    if "borders" in tokens and "radius" in tokens["borders"]:
        extend["borderRadius"] = tokens["borders"]["radius"]

    # Shadows
    if "shadows" in tokens:
        extend["boxShadow"] = tokens["shadows"]

    # Animation
    if "animation" in tokens:
        if "duration" in tokens["animation"]:
            extend["transitionDuration"] = tokens["animation"]["duration"]
        if "easing" in tokens["animation"]:
            extend["transitionTimingFunction"] = tokens["animation"]["easing"]

    # Generate output
    output = f"""/** @type {{import('tailwindcss').Config}} */
export default {json.dumps(config, indent=2)}
"""
    return output


def generate_tailwind_config_with_css_vars(tokens: dict) -> str:
    """
    Generate tailwind.config.js that references CSS variables.

    This approach allows runtime theme switching.
    """
    config = {
        "content": [
            "./index.html",
            "./src/**/*.{js,ts,jsx,tsx,vue}",
        ],
        "theme": {
            "extend": {
                "colors": {
                    "primary": {
                        "50": "var(--color-primary-50)",
                        "100": "var(--color-primary-100)",
                        "200": "var(--color-primary-200)",
                        "300": "var(--color-primary-300)",
                        "400": "var(--color-primary-400)",
                        "500": "var(--color-primary-500)",
                        "600": "var(--color-primary-600)",
                        "700": "var(--color-primary-700)",
                        "800": "var(--color-primary-800)",
                        "900": "var(--color-primary-900)",
                        "950": "var(--color-primary-950)",
                    },
                    "secondary": {
                        "50": "var(--color-secondary-50)",
                        "500": "var(--color-secondary-500)",
                        "900": "var(--color-secondary-900)",
                    },
                    "success": "var(--color-success)",
                    "error": "var(--color-error)",
                    "warning": "var(--color-warning)",
                    "info": "var(--color-info)",
                },
                "fontFamily": {
                    "sans": "var(--font-sans)",
                    "serif": "var(--font-serif)",
                    "mono": "var(--font-mono)",
                },
                "borderRadius": {
                    "sm": "var(--radius-sm)",
                    "DEFAULT": "var(--radius-default)",
                    "md": "var(--radius-md)",
                    "lg": "var(--radius-lg)",
                    "xl": "var(--radius-xl)",
                    "full": "var(--radius-full)",
                },
                "boxShadow": {
                    "sm": "var(--shadow-sm)",
                    "DEFAULT": "var(--shadow-default)",
                    "md": "var(--shadow-md)",
                    "lg": "var(--shadow-lg)",
                },
            }
        },
        "plugins": []
    }

    return f"""/** @type {{import('tailwindcss').Config}} */
export default {json.dumps(config, indent=2)}
"""


def generate_css_variables(tokens: dict, include_dark_mode: bool = True) -> str:
    """
    Generate CSS custom properties (variables) from design tokens.

    Args:
        tokens: Normalized design tokens dictionary
        include_dark_mode: Whether to include dark mode variants

    Returns:
        String content for CSS file
    """
    lines = [":root {"]

    # Colors
    if "colors" in tokens:
        lines.append("  /* ===== Colors ===== */")
        lines.append("")

        for category, scale in tokens["colors"].items():
            if category == "semantic":
                lines.append("  /* Semantic Colors */")
                for name, variants in scale.items():
                    if isinstance(variants, dict):
                        for variant, value in variants.items():
                            if variant == "DEFAULT":
                                lines.append(f"  --color-{name}: {value};")
                            else:
                                lines.append(f"  --color-{name}-{variant}: {value};")
                    else:
                        lines.append(f"  --color-{name}: {variants};")
            else:
                lines.append(f"  /* {category.title()} Palette */")
                if isinstance(scale, dict):
                    for shade, value in scale.items():
                        lines.append(f"  --color-{category}-{shade}: {value};")
            lines.append("")

    # Typography
    if "typography" in tokens:
        lines.append("  /* ===== Typography ===== */")
        lines.append("")

        # Font families
        if "fontFamily" in tokens["typography"]:
            lines.append("  /* Font Families */")
            for family, stack in tokens["typography"]["fontFamily"].items():
                if isinstance(stack, list):
                    value = ", ".join(f"'{f}'" if " " in f else f for f in stack)
                else:
                    value = f"'{stack}'" if " " in stack else stack
                lines.append(f"  --font-{family}: {value};")
            lines.append("")

        # Font sizes
        if "fontSize" in tokens["typography"]:
            lines.append("  /* Font Sizes */")
            for size, value in tokens["typography"]["fontSize"].items():
                if isinstance(value, dict):
                    lines.append(f"  --font-size-{size}: {value.get('value', '1rem')};")
                    if "lineHeight" in value:
                        lines.append(f"  --line-height-{size}: {value['lineHeight']};")
                else:
                    lines.append(f"  --font-size-{size}: {value};")
            lines.append("")

        # Font weights
        if "fontWeight" in tokens["typography"]:
            lines.append("  /* Font Weights */")
            for weight, value in tokens["typography"]["fontWeight"].items():
                lines.append(f"  --font-weight-{weight}: {value};")
            lines.append("")

    # Spacing
    if "spacing" in tokens:
        lines.append("  /* ===== Spacing ===== */")
        for key, value in tokens["spacing"].items():
            safe_key = key.replace(".", "-")
            lines.append(f"  --spacing-{safe_key}: {value};")
        lines.append("")

    # Borders
    if "borders" in tokens:
        lines.append("  /* ===== Borders ===== */")
        if "radius" in tokens["borders"]:
            for key, value in tokens["borders"]["radius"].items():
                lines.append(f"  --radius-{key.lower()}: {value};")
        if "width" in tokens["borders"]:
            for key, value in tokens["borders"]["width"].items():
                lines.append(f"  --border-width-{key.lower()}: {value};")
        lines.append("")

    # Shadows
    if "shadows" in tokens:
        lines.append("  /* ===== Shadows ===== */")
        for key, value in tokens["shadows"].items():
            lines.append(f"  --shadow-{key.lower()}: {value};")
        lines.append("")

    # Animation
    if "animation" in tokens:
        lines.append("  /* ===== Animation ===== */")
        if "duration" in tokens["animation"]:
            for key, value in tokens["animation"]["duration"].items():
                lines.append(f"  --duration-{key}: {value};")
        if "easing" in tokens["animation"]:
            for key, value in tokens["animation"]["easing"].items():
                lines.append(f"  --easing-{key}: {value};")
        lines.append("")

    lines.append("}")

    # Dark mode
    if include_dark_mode:
        lines.append("")
        lines.append("/* Dark Mode */")
        lines.append("@media (prefers-color-scheme: dark) {")
        lines.append("  :root {")
        lines.append("    /* Override colors for dark mode */")
        lines.append("    /* Primary colors - lighter variants */")

        # Swap light/dark neutral colors
        if "colors" in tokens and "neutral" in tokens["colors"]:
            neutral = tokens["colors"]["neutral"]
            lines.append(f"    --color-neutral-50: {neutral.get('950', '#0A0A0A')};")
            lines.append(f"    --color-neutral-100: {neutral.get('900', '#171717')};")
            lines.append(f"    --color-neutral-800: {neutral.get('100', '#F5F5F5')};")
            lines.append(f"    --color-neutral-900: {neutral.get('50', '#FAFAFA')};")

        lines.append("  }")
        lines.append("}")

    return "\n".join(lines)


def generate_shadcn_theme(tokens: dict) -> tuple[str, str]:
    """
    Generate Shadcn UI theme files (components.json and CSS variables).

    Args:
        tokens: Normalized design tokens dictionary

    Returns:
        Tuple of (components.json content, CSS additions)
    """
    components_json = {
        "$schema": "https://ui.shadcn.com/schema.json",
        "style": "default",
        "rsc": True,
        "tsx": True,
        "tailwind": {
            "config": "tailwind.config.ts",
            "css": "src/styles/globals.css",
            "baseColor": "slate",
            "cssVariables": True,
            "prefix": ""
        },
        "aliases": {
            "components": "@/components",
            "utils": "@/lib/utils",
            "ui": "@/components/ui",
            "lib": "@/lib",
            "hooks": "@/hooks"
        }
    }

    # Convert colors to HSL for Shadcn format
    css_lines = ["@layer base {", "  :root {"]

    if "colors" in tokens:
        primary = tokens["colors"].get("primary", {})
        neutral = tokens["colors"].get("neutral", {})
        semantic = tokens["colors"].get("semantic", {})

        # Convert primary color
        primary_500 = primary.get("500", "#3B82F6")
        h, s, l = hex_to_hsl(primary_500)
        css_lines.append(f"    --primary: {h} {s}% {l}%;")
        css_lines.append(f"    --primary-foreground: 210 40% 98%;")

        # Background and foreground from neutral
        bg_color = neutral.get("50", "#FFFFFF")
        fg_color = neutral.get("900", "#171717")
        h, s, l = hex_to_hsl(bg_color)
        css_lines.append(f"    --background: {h} {s}% {l}%;")
        h, s, l = hex_to_hsl(fg_color)
        css_lines.append(f"    --foreground: {h} {s}% {l}%;")

        # Card colors
        css_lines.append(f"    --card: {hex_to_hsl_str(neutral.get('50', '#FFFFFF'))};")
        css_lines.append(f"    --card-foreground: {hex_to_hsl_str(fg_color)};")

        # Muted colors
        muted_color = neutral.get("100", "#F5F5F5")
        muted_fg = neutral.get("500", "#737373")
        css_lines.append(f"    --muted: {hex_to_hsl_str(muted_color)};")
        css_lines.append(f"    --muted-foreground: {hex_to_hsl_str(muted_fg)};")

        # Border and input
        border_color = neutral.get("200", "#E5E5E5")
        css_lines.append(f"    --border: {hex_to_hsl_str(border_color)};")
        css_lines.append(f"    --input: {hex_to_hsl_str(border_color)};")

        # Ring
        css_lines.append(f"    --ring: {hex_to_hsl_str(primary_500)};")

        # Destructive (error)
        error = semantic.get("error", {})
        error_color = error.get("DEFAULT", "#EF4444") if isinstance(error, dict) else error
        css_lines.append(f"    --destructive: {hex_to_hsl_str(error_color)};")
        css_lines.append(f"    --destructive-foreground: 210 40% 98%;")

        # Radius
        if "borders" in tokens and "radius" in tokens["borders"]:
            radius = tokens["borders"]["radius"].get("md", "0.375rem")
            css_lines.append(f"    --radius: {radius};")

    css_lines.append("  }")

    # Dark mode
    css_lines.append("")
    css_lines.append("  .dark {")
    if "colors" in tokens:
        neutral = tokens["colors"].get("neutral", {})
        css_lines.append(f"    --background: {hex_to_hsl_str(neutral.get('900', '#171717'))};")
        css_lines.append(f"    --foreground: {hex_to_hsl_str(neutral.get('50', '#FAFAFA'))};")
        css_lines.append(f"    --card: {hex_to_hsl_str(neutral.get('800', '#262626'))};")
        css_lines.append(f"    --card-foreground: {hex_to_hsl_str(neutral.get('50', '#FAFAFA'))};")
        css_lines.append(f"    --muted: {hex_to_hsl_str(neutral.get('800', '#262626'))};")
        css_lines.append(f"    --muted-foreground: {hex_to_hsl_str(neutral.get('400', '#A3A3A3'))};")
        css_lines.append(f"    --border: {hex_to_hsl_str(neutral.get('700', '#404040'))};")
        css_lines.append(f"    --input: {hex_to_hsl_str(neutral.get('700', '#404040'))};")
    css_lines.append("  }")

    css_lines.append("}")

    return json.dumps(components_json, indent=2), "\n".join(css_lines)


def hex_to_hsl(hex_color: str) -> tuple[int, int, int]:
    """
    Convert hex color to HSL values.

    Returns:
        Tuple of (hue, saturation%, lightness%)
    """
    hex_val = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_val[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    max_c = max(r, g, b)
    min_c = min(r, g, b)
    l = (max_c + min_c) / 2.0

    if max_c == min_c:
        h = s = 0.0
    else:
        d = max_c - min_c
        s = d / (2.0 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)

        if max_c == r:
            h = (g - b) / d + (6.0 if g < b else 0.0)
        elif max_c == g:
            h = (b - r) / d + 2.0
        else:
            h = (r - g) / d + 4.0
        h /= 6.0

    return round(h * 360), round(s * 100), round(l * 100)


def hex_to_hsl_str(hex_color: str) -> str:
    """Convert hex to HSL string format for CSS."""
    h, s, l = hex_to_hsl(hex_color)
    return f"{h} {s}% {l}%"


def generate_vue_variables(tokens: dict) -> str:
    """
    Generate CSS variables optimized for Vue projects.

    Similar to standard CSS variables but with Vue-specific comments.
    """
    return generate_css_variables(tokens, include_dark_mode=True)


if __name__ == "__main__":
    # Test with sample tokens
    sample_tokens = {
        "colors": {
            "primary": {
                "500": "#3B82F6",
            },
            "neutral": {
                "50": "#FAFAFA",
                "100": "#F5F5F5",
                "500": "#737373",
                "900": "#171717",
            },
            "semantic": {
                "success": {"DEFAULT": "#22C55E"},
                "error": {"DEFAULT": "#EF4444"},
            }
        },
        "typography": {
            "fontFamily": {
                "sans": ["Inter", "sans-serif"],
            },
            "fontSize": {
                "base": {"value": "1rem", "lineHeight": "1.5rem"},
            }
        },
        "borders": {
            "radius": {
                "md": "0.375rem",
            }
        }
    }

    from normalize_tokens import normalize_tokens

    normalized = normalize_tokens(sample_tokens)

    print("=== Tailwind Config ===")
    print(generate_tailwind_config(normalized)[:500])

    print("\n=== CSS Variables ===")
    print(generate_css_variables(normalized)[:500])

    print("\n=== Shadcn Theme ===")
    components, css = generate_shadcn_theme(normalized)
    print(css[:500])
