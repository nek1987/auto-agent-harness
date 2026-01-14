---
name: design-system-extractor
description: Extract design tokens from reference images, URLs, and Figma files. Analyzes visual references using Claude Vision API to create unified design systems. Use when redesigning frontend, migrating design systems, or extracting tokens from mockups.
---

# Design System Extractor

A comprehensive skill for extracting design tokens from visual references (images, screenshots, URLs, Figma files) and transforming them into usable design system configurations for React, Vue, Tailwind CSS, and Shadcn UI.

## When to Use This Skill

Activate this skill when users request:
- Complete frontend redesign based on references
- Design system extraction from mockups or screenshots
- Color palette extraction from images
- Typography analysis from visual references
- Migration from one design system to another
- Creating consistent design tokens from multiple reference sources

**Trigger phrases:**
- "Redesign the frontend based on this reference"
- "Extract design tokens from this image"
- "Create a design system from this mockup"
- "Change the color scheme to match this"
- "Migrate to a new design system"

---

## Core Capabilities

### 1. Reference Analysis

The extractor can process three types of references:

#### Images (PNG/JPG/WebP)
- Screenshots of existing interfaces
- Design mockups from Figma exports
- Photos of competitor products
- Mood boards and inspiration images

#### URLs
- Live websites (captured via Playwright screenshots)
- Design system documentation pages
- Component library showcases

#### Figma Files (via MCP)
- Direct token extraction from Figma variables
- Component style analysis
- Frame-by-frame design inspection

### 2. Token Extraction Process

```
Reference Input → Vision Analysis → Raw Tokens → Normalization → Output Format
```

**Vision Analysis Prompt Template:**
```markdown
Analyze this UI design image and extract design tokens:

## Colors
Identify all colors and categorize them:
- **Primary**: Main brand/accent colors (buttons, links, highlights)
- **Secondary**: Supporting accent colors
- **Neutral**: Grays, blacks, whites (backgrounds, text, borders)
- **Semantic**: Success (green), Error (red), Warning (yellow/orange), Info (blue)

For each color, provide:
- Hex value (e.g., #3B82F6)
- Suggested token name (e.g., primary-500)
- Usage context (e.g., "primary button background")

## Typography
Identify typography patterns:
- Font families (if recognizable, otherwise suggest similar web-safe fonts)
- Font sizes in pixels (estimate from visual hierarchy)
- Font weights (light, regular, medium, semibold, bold)
- Line heights (tight, normal, relaxed)

## Spacing
Analyze spacing patterns:
- Base unit (typically 4px or 8px)
- Common spacing values used
- Padding patterns in components
- Gap sizes between elements

## Borders
Identify border patterns:
- Border radius values (sharp, rounded, pill)
- Border widths
- Border colors and styles

## Shadows
Describe shadow effects:
- Elevation levels (subtle, medium, prominent)
- Shadow colors and opacity
- Blur and spread values

## Output Format
Return as structured JSON following the Design Tokens Schema.
```

---

## Design Tokens Schema

### Complete Schema

```json
{
  "$schema": "design-tokens-v1",
  "meta": {
    "name": "Extracted Design System",
    "source": "reference-image.png",
    "extractedAt": "2025-01-14T12:00:00Z",
    "confidence": 0.85
  },
  "colors": {
    "primary": {
      "50": "#EFF6FF",
      "100": "#DBEAFE",
      "200": "#BFDBFE",
      "300": "#93C5FD",
      "400": "#60A5FA",
      "500": "#3B82F6",
      "600": "#2563EB",
      "700": "#1D4ED8",
      "800": "#1E40AF",
      "900": "#1E3A8A",
      "950": "#172554"
    },
    "secondary": {
      "50": "#...",
      "500": "#...",
      "900": "#..."
    },
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
      "950": "#0A0A0A"
    },
    "semantic": {
      "success": {
        "light": "#DCFCE7",
        "DEFAULT": "#22C55E",
        "dark": "#166534"
      },
      "error": {
        "light": "#FEE2E2",
        "DEFAULT": "#EF4444",
        "dark": "#991B1B"
      },
      "warning": {
        "light": "#FEF3C7",
        "DEFAULT": "#F59E0B",
        "dark": "#92400E"
      },
      "info": {
        "light": "#DBEAFE",
        "DEFAULT": "#3B82F6",
        "dark": "#1E40AF"
      }
    }
  },
  "typography": {
    "fontFamily": {
      "sans": ["Inter", "system-ui", "sans-serif"],
      "serif": ["Georgia", "Cambria", "serif"],
      "mono": ["JetBrains Mono", "Consolas", "monospace"],
      "display": ["Space Grotesk", "sans-serif"]
    },
    "fontSize": {
      "xs": { "value": "0.75rem", "lineHeight": "1rem" },
      "sm": { "value": "0.875rem", "lineHeight": "1.25rem" },
      "base": { "value": "1rem", "lineHeight": "1.5rem" },
      "lg": { "value": "1.125rem", "lineHeight": "1.75rem" },
      "xl": { "value": "1.25rem", "lineHeight": "1.75rem" },
      "2xl": { "value": "1.5rem", "lineHeight": "2rem" },
      "3xl": { "value": "1.875rem", "lineHeight": "2.25rem" },
      "4xl": { "value": "2.25rem", "lineHeight": "2.5rem" },
      "5xl": { "value": "3rem", "lineHeight": "1" }
    },
    "fontWeight": {
      "thin": 100,
      "light": 300,
      "normal": 400,
      "medium": 500,
      "semibold": 600,
      "bold": 700,
      "extrabold": 800
    },
    "lineHeight": {
      "none": 1,
      "tight": 1.25,
      "snug": 1.375,
      "normal": 1.5,
      "relaxed": 1.625,
      "loose": 2
    },
    "letterSpacing": {
      "tighter": "-0.05em",
      "tight": "-0.025em",
      "normal": "0em",
      "wide": "0.025em",
      "wider": "0.05em",
      "widest": "0.1em"
    }
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
    "32": "8rem"
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
      "full": "9999px"
    },
    "width": {
      "0": "0px",
      "DEFAULT": "1px",
      "2": "2px",
      "4": "4px",
      "8": "8px"
    }
  },
  "shadows": {
    "sm": "0 1px 2px 0 rgb(0 0 0 / 0.05)",
    "DEFAULT": "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
    "md": "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
    "lg": "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
    "xl": "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
    "2xl": "0 25px 50px -12px rgb(0 0 0 / 0.25)",
    "inner": "inset 0 2px 4px 0 rgb(0 0 0 / 0.05)",
    "none": "0 0 #0000"
  },
  "animation": {
    "duration": {
      "fast": "150ms",
      "normal": "300ms",
      "slow": "500ms"
    },
    "easing": {
      "linear": "linear",
      "in": "cubic-bezier(0.4, 0, 1, 1)",
      "out": "cubic-bezier(0, 0, 0.2, 1)",
      "in-out": "cubic-bezier(0.4, 0, 0.2, 1)",
      "spring": "cubic-bezier(0.175, 0.885, 0.32, 1.275)"
    }
  }
}
```

---

## Output Formats

### Tailwind CSS Config

```javascript
// tailwind.config.js
export default {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#EFF6FF',
          // ... full palette
        },
        // ... other colors
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // ...
      },
      // ... other tokens
    }
  }
}
```

### CSS Variables

```css
/* globals.css or variables.css */
:root {
  /* Colors */
  --color-primary-50: #EFF6FF;
  --color-primary-500: #3B82F6;
  --color-primary-900: #1E3A8A;

  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-size-base: 1rem;
  --font-weight-normal: 400;

  /* Spacing */
  --spacing-1: 0.25rem;
  --spacing-4: 1rem;

  /* Borders */
  --radius-md: 0.375rem;

  /* Shadows */
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --color-primary-500: #60A5FA;
    /* ... dark variants */
  }
}
```

### Shadcn UI Theme

```json
{
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/styles/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

---

## Redesign Workflow

### Phase 1: Reference Collection
1. User uploads images, provides URLs, or links Figma files
2. System validates and stores references
3. URLs are screenshotted via Playwright

### Phase 2: Token Extraction
1. Each reference is analyzed via Claude Vision API
2. Raw tokens are extracted using the vision prompt
3. Tokens are normalized to the schema
4. Conflicts between references are resolved (priority or merge)

### Phase 3: Plan Generation
1. Detect project framework (React/Vue/Tailwind/etc.)
2. Identify files to modify:
   - `globals.css` or `variables.css`
   - `tailwind.config.js` or `tailwind.config.ts`
   - Theme files (shadcn, MUI, etc.)
   - Component files with inline styles
3. Generate diff preview for each file

### Phase 4: User Approval
1. Present extracted tokens with visual preview
2. Allow editing of token values
3. Show file change plan with diffs
4. User approves or modifies each phase

### Phase 5: Implementation
Apply changes in order:
1. **Global styles** - CSS variables, base styles
2. **Config files** - Tailwind config, theme config
3. **Components** - Update component-level styles
4. **Pages** - Update page-specific styles

### Phase 6: Verification
1. Take before/after screenshots
2. Highlight visual differences
3. Run visual regression tests
4. User confirms redesign is successful

---

## Best Practices

### Color Extraction
- Extract dominant colors using color clustering
- Generate full color palettes (50-950) from single colors
- Ensure sufficient contrast ratios (WCAG AA)
- Preserve semantic meaning (success=green, error=red)

### Typography
- Map unknown fonts to similar web-safe alternatives
- Maintain consistent type scale (1.25 or 1.333 ratio)
- Preserve weight hierarchy
- Consider readability at all sizes

### Spacing
- Identify base spacing unit (4px or 8px)
- Generate consistent spacing scale
- Maintain proportional relationships
- Consider component-level vs page-level spacing

### Implementation
- Always backup before modifications
- Apply changes atomically (one file at a time)
- Test after each phase
- Provide rollback capability

---

## Integration with Auto-Agent-Harness

This skill integrates with the auto-agent-harness system:

1. **MCP Tools**: Use `redesign_start_session`, `redesign_extract_tokens`, etc.
2. **Feature Type**: Create "redesign" features in the kanban board
3. **Approval Gates**: Pause for user approval at each phase
4. **WebSocket Updates**: Real-time progress via WebSocket

---

## Resources

- [Design Tokens Format](https://design-tokens.github.io/community-group/format/)
- [Tailwind CSS Configuration](https://tailwindcss.com/docs/configuration)
- [Shadcn UI Theming](https://ui.shadcn.com/docs/theming)
- [WCAG Color Contrast](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
- [Claude Vision API](https://docs.anthropic.com/claude/docs/vision)
