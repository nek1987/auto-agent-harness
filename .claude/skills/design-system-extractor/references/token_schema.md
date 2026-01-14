# Design Tokens Schema Reference

This document defines the JSON schema for extracted design tokens.

## Schema Version

Current version: `design-tokens-v1`

## Complete JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Design Tokens Schema",
  "type": "object",
  "required": ["colors", "typography", "spacing"],
  "properties": {
    "$schema": {
      "type": "string",
      "const": "design-tokens-v1"
    },
    "meta": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "source": { "type": "string" },
        "extractedAt": { "type": "string", "format": "date-time" },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "colors": {
      "$ref": "#/definitions/ColorTokens"
    },
    "typography": {
      "$ref": "#/definitions/TypographyTokens"
    },
    "spacing": {
      "$ref": "#/definitions/SpacingTokens"
    },
    "borders": {
      "$ref": "#/definitions/BorderTokens"
    },
    "shadows": {
      "$ref": "#/definitions/ShadowTokens"
    },
    "animation": {
      "$ref": "#/definitions/AnimationTokens"
    }
  },
  "definitions": {
    "ColorScale": {
      "type": "object",
      "properties": {
        "50": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "100": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "200": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "300": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "400": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "500": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "600": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "700": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "800": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "900": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "950": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" }
      }
    },
    "SemanticColor": {
      "type": "object",
      "properties": {
        "light": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "DEFAULT": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "dark": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" }
      },
      "required": ["DEFAULT"]
    },
    "ColorTokens": {
      "type": "object",
      "properties": {
        "primary": { "$ref": "#/definitions/ColorScale" },
        "secondary": { "$ref": "#/definitions/ColorScale" },
        "neutral": { "$ref": "#/definitions/ColorScale" },
        "semantic": {
          "type": "object",
          "properties": {
            "success": { "$ref": "#/definitions/SemanticColor" },
            "error": { "$ref": "#/definitions/SemanticColor" },
            "warning": { "$ref": "#/definitions/SemanticColor" },
            "info": { "$ref": "#/definitions/SemanticColor" }
          }
        }
      },
      "required": ["primary", "neutral"]
    },
    "FontSize": {
      "type": "object",
      "properties": {
        "value": { "type": "string" },
        "lineHeight": { "type": "string" }
      },
      "required": ["value"]
    },
    "TypographyTokens": {
      "type": "object",
      "properties": {
        "fontFamily": {
          "type": "object",
          "properties": {
            "sans": { "type": "array", "items": { "type": "string" } },
            "serif": { "type": "array", "items": { "type": "string" } },
            "mono": { "type": "array", "items": { "type": "string" } },
            "display": { "type": "array", "items": { "type": "string" } }
          }
        },
        "fontSize": {
          "type": "object",
          "additionalProperties": { "$ref": "#/definitions/FontSize" }
        },
        "fontWeight": {
          "type": "object",
          "additionalProperties": { "type": "integer", "minimum": 100, "maximum": 900 }
        },
        "lineHeight": {
          "type": "object",
          "additionalProperties": { "type": "number" }
        },
        "letterSpacing": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        }
      }
    },
    "SpacingTokens": {
      "type": "object",
      "additionalProperties": { "type": "string" }
    },
    "BorderTokens": {
      "type": "object",
      "properties": {
        "radius": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        },
        "width": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        }
      }
    },
    "ShadowTokens": {
      "type": "object",
      "additionalProperties": { "type": "string" }
    },
    "AnimationTokens": {
      "type": "object",
      "properties": {
        "duration": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        },
        "easing": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        }
      }
    }
  }
}
```

## Minimal Valid Example

```json
{
  "$schema": "design-tokens-v1",
  "colors": {
    "primary": {
      "500": "#3B82F6"
    },
    "neutral": {
      "100": "#F5F5F5",
      "900": "#171717"
    }
  },
  "typography": {
    "fontFamily": {
      "sans": ["Inter", "sans-serif"]
    },
    "fontSize": {
      "base": { "value": "1rem" }
    }
  },
  "spacing": {
    "4": "1rem"
  }
}
```

## Color Scale Generation

When only a single color is provided (e.g., primary: "#3B82F6"), generate the full scale:

```python
def generate_color_scale(base_color: str) -> dict:
    """
    Generate a full color scale from a single color.

    Uses HSL manipulation:
    - 50: lightness 97%
    - 100: lightness 94%
    - 200: lightness 86%
    - 300: lightness 76%
    - 400: lightness 64%
    - 500: base color (lightness ~50%)
    - 600: lightness 42%
    - 700: lightness 34%
    - 800: lightness 26%
    - 900: lightness 20%
    - 950: lightness 12%
    """
```

## Validation Rules

1. **Colors**: All color values must be valid hex codes (#RRGGBB)
2. **Typography**: Font sizes should be in rem or px
3. **Spacing**: Values should follow a consistent scale (4px or 8px base)
4. **Borders**: Radius values should increase proportionally
5. **Shadows**: Must be valid CSS box-shadow syntax
