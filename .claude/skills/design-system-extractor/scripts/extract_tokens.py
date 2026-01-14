#!/usr/bin/env python3
"""
Design Token Extraction from Images

This script provides functions for extracting design tokens from images
using Claude's Vision API. It analyzes visual references and returns
structured design token data.

Usage:
    from extract_tokens import extract_tokens_from_image

    tokens = await extract_tokens_from_image(image_base64, anthropic_client)
"""

import json
import re
from typing import Any


# Vision API prompt for token extraction
EXTRACTION_PROMPT = """Analyze this UI design image and extract design tokens.

## Your Task
Extract all visual design elements and output them as structured JSON following the schema below.

## Color Extraction
Identify all colors used in the design:
1. **Primary colors**: Main brand/accent colors (buttons, links, active states)
2. **Secondary colors**: Supporting accent colors
3. **Neutral colors**: Grays, blacks, whites (backgrounds, text, borders)
4. **Semantic colors**: Success (green), Error (red), Warning (yellow/orange), Info (blue)

For each color:
- Extract the exact hex value if possible
- If you can only see one shade, provide that as the "500" value
- Try to identify if light/dark variants are visible

## Typography Extraction
Identify typography patterns:
1. **Font families**: Identify or suggest similar web fonts
2. **Font sizes**: Estimate sizes in pixels based on visual hierarchy
3. **Font weights**: Identify light, regular, medium, semibold, bold usage
4. **Line heights**: Estimate tight, normal, or relaxed spacing

## Spacing Extraction
Analyze spacing patterns:
1. **Base unit**: Identify if 4px or 8px grid is used
2. **Common values**: List frequently used spacing values
3. **Component padding**: Note padding patterns in cards, buttons, inputs

## Border Extraction
Identify border styles:
1. **Radius**: Sharp (0), slightly rounded (4px), rounded (8px), pill (full)
2. **Width**: Hairline (1px), medium (2px), thick (3px+)

## Shadow Extraction
Describe shadows:
1. **Elevation levels**: None, subtle, medium, prominent
2. **Style**: Soft blur, hard edge, colored shadow

## Output Format
Return ONLY valid JSON matching this structure:

```json
{
  "$schema": "design-tokens-v1",
  "meta": {
    "confidence": 0.0-1.0,
    "notes": "any observations about the design"
  },
  "colors": {
    "primary": {
      "500": "#HEXVAL"
    },
    "secondary": {
      "500": "#HEXVAL"
    },
    "neutral": {
      "50": "#HEXVAL",
      "100": "#HEXVAL",
      "500": "#HEXVAL",
      "900": "#HEXVAL"
    },
    "semantic": {
      "success": {"DEFAULT": "#HEXVAL"},
      "error": {"DEFAULT": "#HEXVAL"},
      "warning": {"DEFAULT": "#HEXVAL"},
      "info": {"DEFAULT": "#HEXVAL"}
    }
  },
  "typography": {
    "fontFamily": {
      "sans": ["Font Name", "fallback"],
      "mono": ["Mono Font", "monospace"]
    },
    "fontSize": {
      "sm": {"value": "14px"},
      "base": {"value": "16px"},
      "lg": {"value": "18px"},
      "xl": {"value": "24px"},
      "2xl": {"value": "32px"}
    },
    "fontWeight": {
      "normal": 400,
      "medium": 500,
      "bold": 700
    }
  },
  "spacing": {
    "1": "4px",
    "2": "8px",
    "4": "16px",
    "6": "24px",
    "8": "32px"
  },
  "borders": {
    "radius": {
      "sm": "4px",
      "md": "8px",
      "lg": "16px",
      "full": "9999px"
    }
  },
  "shadows": {
    "sm": "0 1px 2px rgba(0,0,0,0.05)",
    "md": "0 4px 6px rgba(0,0,0,0.1)",
    "lg": "0 10px 15px rgba(0,0,0,0.1)"
  }
}
```

Important:
- Only include tokens you can actually identify from the image
- Use your best judgment for values you can estimate
- Set confidence based on how clear the design elements are
- Prefer common web-safe values (4px increments, standard font sizes)
"""


async def extract_tokens_from_image(
    image_base64: str,
    anthropic_client: Any,
    media_type: str = "image/png"
) -> dict:
    """
    Extract design tokens from a base64-encoded image using Claude Vision.

    Args:
        image_base64: Base64-encoded image data (without data: prefix)
        anthropic_client: Anthropic API client instance
        media_type: MIME type of the image (image/png, image/jpeg, image/webp)

    Returns:
        Dictionary containing extracted design tokens
    """
    message = await anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    # Extract JSON from response
    response_text = message.content[0].text
    tokens = parse_json_from_response(response_text)

    return tokens


def parse_json_from_response(response_text: str) -> dict:
    """
    Extract JSON from Claude's response text.

    Handles cases where JSON is wrapped in markdown code blocks.
    """
    # Try to find JSON in code blocks first
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)

    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON object
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError("No JSON found in response")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in response: {e}")


def validate_tokens(tokens: dict) -> tuple[bool, list[str]]:
    """
    Validate extracted tokens against the schema.

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check required fields
    if "colors" not in tokens:
        errors.append("Missing 'colors' field")
    elif "primary" not in tokens.get("colors", {}):
        errors.append("Missing 'colors.primary' field")

    if "typography" not in tokens:
        errors.append("Missing 'typography' field")

    if "spacing" not in tokens:
        errors.append("Missing 'spacing' field")

    # Validate color hex values
    hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for category, colors in tokens.get("colors", {}).items():
        if isinstance(colors, dict):
            for shade, value in colors.items():
                if isinstance(value, str) and not hex_pattern.match(value):
                    errors.append(f"Invalid hex color: colors.{category}.{shade} = {value}")
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, str) and not hex_pattern.match(sub_value):
                            errors.append(f"Invalid hex color: colors.{category}.{shade}.{sub_key}")

    return len(errors) == 0, errors


def generate_color_scale(base_color: str) -> dict:
    """
    Generate a full color scale (50-950) from a single base color.

    Uses HSL manipulation to create lighter and darker variants.

    Args:
        base_color: Hex color string (e.g., "#3B82F6")

    Returns:
        Dictionary with color scale (50, 100, 200, ..., 900, 950)
    """
    # Convert hex to RGB
    hex_val = base_color.lstrip("#")
    r, g, b = tuple(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))

    # Convert RGB to HSL
    r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
    max_c = max(r_norm, g_norm, b_norm)
    min_c = min(r_norm, g_norm, b_norm)
    l = (max_c + min_c) / 2.0

    if max_c == min_c:
        h = s = 0.0
    else:
        d = max_c - min_c
        s = d / (2.0 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)

        if max_c == r_norm:
            h = (g_norm - b_norm) / d + (6.0 if g_norm < b_norm else 0.0)
        elif max_c == g_norm:
            h = (b_norm - r_norm) / d + 2.0
        else:
            h = (r_norm - g_norm) / d + 4.0
        h /= 6.0

    # Define lightness values for each shade
    lightness_map = {
        "50": 0.97,
        "100": 0.94,
        "200": 0.86,
        "300": 0.76,
        "400": 0.64,
        "500": l,  # Keep original lightness for 500
        "600": 0.42,
        "700": 0.34,
        "800": 0.26,
        "900": 0.20,
        "950": 0.12,
    }

    def hsl_to_hex(h: float, s: float, l: float) -> str:
        """Convert HSL to hex color."""

        def hue_to_rgb(p: float, q: float, t: float) -> float:
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1 / 6:
                return p + (q - p) * 6 * t
            if t < 1 / 2:
                return q
            if t < 2 / 3:
                return p + (q - p) * (2 / 3 - t) * 6
            return p

        if s == 0:
            r = g = b = l
        else:
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1 / 3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1 / 3)

        return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"

    # Generate scale
    scale = {}
    for shade, target_l in lightness_map.items():
        # Adjust saturation for very light/dark shades
        adjusted_s = s
        if target_l > 0.9:
            adjusted_s = s * 0.3  # Reduce saturation for very light
        elif target_l < 0.2:
            adjusted_s = s * 0.7  # Slightly reduce for very dark

        scale[shade] = hsl_to_hex(h, adjusted_s, target_l)

    return scale


if __name__ == "__main__":
    # Test color scale generation
    test_color = "#3B82F6"  # Blue
    scale = generate_color_scale(test_color)
    print(f"Color scale for {test_color}:")
    for shade, color in scale.items():
        print(f"  {shade}: {color}")
