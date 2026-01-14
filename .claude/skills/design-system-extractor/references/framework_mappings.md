# Framework Mappings Reference

This document shows how design tokens are mapped to different frontend frameworks.

## Supported Frameworks

| Framework | Styling | Output Files |
|-----------|---------|--------------|
| React + Tailwind | Tailwind CSS | `tailwind.config.js`, `globals.css` |
| React + CSS Modules | CSS Variables | `variables.css`, component `.module.css` |
| Vue + Tailwind | Tailwind CSS | `tailwind.config.js`, `main.css` |
| Vue + Scoped CSS | CSS Variables | `variables.css`, component `<style scoped>` |
| Shadcn UI | Tailwind + CSS Variables | `globals.css`, `components.json` |
| Next.js | Tailwind CSS | `tailwind.config.ts`, `globals.css` |

---

## Tailwind CSS Mapping

### tailwind.config.js

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,vue}",
  ],
  theme: {
    extend: {
      // Colors from tokens.colors
      colors: {
        primary: {
          50: 'var(--color-primary-50)',
          100: 'var(--color-primary-100)',
          200: 'var(--color-primary-200)',
          300: 'var(--color-primary-300)',
          400: 'var(--color-primary-400)',
          500: 'var(--color-primary-500)',
          600: 'var(--color-primary-600)',
          700: 'var(--color-primary-700)',
          800: 'var(--color-primary-800)',
          900: 'var(--color-primary-900)',
          950: 'var(--color-primary-950)',
        },
        secondary: {
          // ... same pattern
        },
        success: 'var(--color-success)',
        error: 'var(--color-error)',
        warning: 'var(--color-warning)',
        info: 'var(--color-info)',
      },

      // Typography from tokens.typography
      fontFamily: {
        sans: 'var(--font-sans)',
        serif: 'var(--font-serif)',
        mono: 'var(--font-mono)',
        display: 'var(--font-display)',
      },

      fontSize: {
        xs: ['var(--font-size-xs)', { lineHeight: 'var(--line-height-xs)' }],
        sm: ['var(--font-size-sm)', { lineHeight: 'var(--line-height-sm)' }],
        base: ['var(--font-size-base)', { lineHeight: 'var(--line-height-base)' }],
        lg: ['var(--font-size-lg)', { lineHeight: 'var(--line-height-lg)' }],
        xl: ['var(--font-size-xl)', { lineHeight: 'var(--line-height-xl)' }],
        '2xl': ['var(--font-size-2xl)', { lineHeight: 'var(--line-height-2xl)' }],
        '3xl': ['var(--font-size-3xl)', { lineHeight: 'var(--line-height-3xl)' }],
        '4xl': ['var(--font-size-4xl)', { lineHeight: 'var(--line-height-4xl)' }],
      },

      // Borders from tokens.borders
      borderRadius: {
        none: 'var(--radius-none)',
        sm: 'var(--radius-sm)',
        DEFAULT: 'var(--radius-default)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        '3xl': 'var(--radius-3xl)',
        full: 'var(--radius-full)',
      },

      // Shadows from tokens.shadows
      boxShadow: {
        sm: 'var(--shadow-sm)',
        DEFAULT: 'var(--shadow-default)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
        '2xl': 'var(--shadow-2xl)',
        inner: 'var(--shadow-inner)',
        none: 'var(--shadow-none)',
      },

      // Animation from tokens.animation
      transitionDuration: {
        fast: 'var(--duration-fast)',
        normal: 'var(--duration-normal)',
        slow: 'var(--duration-slow)',
      },

      transitionTimingFunction: {
        linear: 'var(--easing-linear)',
        in: 'var(--easing-in)',
        out: 'var(--easing-out)',
        'in-out': 'var(--easing-in-out)',
        spring: 'var(--easing-spring)',
      },
    },
  },
  plugins: [],
}
```

---

## CSS Variables Mapping

### globals.css (or variables.css)

```css
:root {
  /* ===== Colors ===== */

  /* Primary Palette */
  --color-primary-50: #EFF6FF;
  --color-primary-100: #DBEAFE;
  --color-primary-200: #BFDBFE;
  --color-primary-300: #93C5FD;
  --color-primary-400: #60A5FA;
  --color-primary-500: #3B82F6;
  --color-primary-600: #2563EB;
  --color-primary-700: #1D4ED8;
  --color-primary-800: #1E40AF;
  --color-primary-900: #1E3A8A;
  --color-primary-950: #172554;

  /* Secondary Palette */
  --color-secondary-50: #F5F3FF;
  --color-secondary-500: #8B5CF6;
  --color-secondary-900: #4C1D95;

  /* Neutral Palette */
  --color-neutral-50: #FAFAFA;
  --color-neutral-100: #F5F5F5;
  --color-neutral-200: #E5E5E5;
  --color-neutral-300: #D4D4D4;
  --color-neutral-400: #A3A3A3;
  --color-neutral-500: #737373;
  --color-neutral-600: #525252;
  --color-neutral-700: #404040;
  --color-neutral-800: #262626;
  --color-neutral-900: #171717;
  --color-neutral-950: #0A0A0A;

  /* Semantic Colors */
  --color-success-light: #DCFCE7;
  --color-success: #22C55E;
  --color-success-dark: #166534;

  --color-error-light: #FEE2E2;
  --color-error: #EF4444;
  --color-error-dark: #991B1B;

  --color-warning-light: #FEF3C7;
  --color-warning: #F59E0B;
  --color-warning-dark: #92400E;

  --color-info-light: #DBEAFE;
  --color-info: #3B82F6;
  --color-info-dark: #1E40AF;

  /* ===== Typography ===== */

  /* Font Families */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-serif: 'Georgia', 'Cambria', serif;
  --font-mono: 'JetBrains Mono', 'Consolas', monospace;
  --font-display: 'Space Grotesk', sans-serif;

  /* Font Sizes */
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-size-2xl: 1.5rem;
  --font-size-3xl: 1.875rem;
  --font-size-4xl: 2.25rem;
  --font-size-5xl: 3rem;

  /* Line Heights */
  --line-height-xs: 1rem;
  --line-height-sm: 1.25rem;
  --line-height-base: 1.5rem;
  --line-height-lg: 1.75rem;
  --line-height-xl: 1.75rem;
  --line-height-2xl: 2rem;
  --line-height-3xl: 2.25rem;
  --line-height-4xl: 2.5rem;
  --line-height-5xl: 1;

  /* Font Weights */
  --font-weight-thin: 100;
  --font-weight-light: 300;
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  --font-weight-extrabold: 800;

  /* ===== Spacing ===== */
  --spacing-0: 0px;
  --spacing-px: 1px;
  --spacing-0-5: 0.125rem;
  --spacing-1: 0.25rem;
  --spacing-1-5: 0.375rem;
  --spacing-2: 0.5rem;
  --spacing-2-5: 0.625rem;
  --spacing-3: 0.75rem;
  --spacing-3-5: 0.875rem;
  --spacing-4: 1rem;
  --spacing-5: 1.25rem;
  --spacing-6: 1.5rem;
  --spacing-8: 2rem;
  --spacing-10: 2.5rem;
  --spacing-12: 3rem;
  --spacing-16: 4rem;
  --spacing-20: 5rem;
  --spacing-24: 6rem;

  /* ===== Borders ===== */
  --radius-none: 0px;
  --radius-sm: 0.125rem;
  --radius-default: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-xl: 0.75rem;
  --radius-2xl: 1rem;
  --radius-3xl: 1.5rem;
  --radius-full: 9999px;

  --border-width-0: 0px;
  --border-width-default: 1px;
  --border-width-2: 2px;
  --border-width-4: 4px;

  /* ===== Shadows ===== */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-default: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
  --shadow-2xl: 0 25px 50px -12px rgb(0 0 0 / 0.25);
  --shadow-inner: inset 0 2px 4px 0 rgb(0 0 0 / 0.05);
  --shadow-none: 0 0 #0000;

  /* ===== Animation ===== */
  --duration-fast: 150ms;
  --duration-normal: 300ms;
  --duration-slow: 500ms;

  --easing-linear: linear;
  --easing-in: cubic-bezier(0.4, 0, 1, 1);
  --easing-out: cubic-bezier(0, 0, 0.2, 1);
  --easing-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --easing-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

/* Dark Mode */
@media (prefers-color-scheme: dark) {
  :root {
    /* Adjusted colors for dark mode */
    --color-primary-500: #60A5FA;
    --color-neutral-50: #0A0A0A;
    --color-neutral-100: #171717;
    --color-neutral-800: #F5F5F5;
    --color-neutral-900: #FAFAFA;

    /* Adjusted shadows */
    --shadow-default: 0 1px 3px 0 rgb(0 0 0 / 0.3);
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.3);
  }
}
```

---

## Shadcn UI Mapping

### components.json

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/styles/globals.css",
    "baseColor": "slate",
    "cssVariables": true,
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
```

### Shadcn globals.css additions

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 224.3 76.3% 48%;
  }
}
```

---

## Vue Scoped CSS Mapping

### Component template

```vue
<template>
  <button class="btn btn-primary">
    Click me
  </button>
</template>

<style scoped>
.btn {
  padding: var(--spacing-2) var(--spacing-4);
  font-family: var(--font-sans);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--easing-out);
}

.btn-primary {
  background-color: var(--color-primary-500);
  color: white;
}

.btn-primary:hover {
  background-color: var(--color-primary-600);
}
</style>
```

---

## Token to Framework Conversion Functions

```python
def tokens_to_tailwind_config(tokens: dict) -> str:
    """Convert design tokens to tailwind.config.js content"""
    pass

def tokens_to_css_variables(tokens: dict) -> str:
    """Convert design tokens to CSS custom properties"""
    pass

def tokens_to_shadcn_theme(tokens: dict) -> str:
    """Convert design tokens to Shadcn UI theme format"""
    pass

def detect_framework(project_dir: Path) -> str:
    """Detect project framework from package.json and file structure"""
    pass
```

---

## File Detection Patterns

| Framework | Detection Pattern |
|-----------|-------------------|
| React | `react` in package.json dependencies |
| Vue | `vue` in package.json dependencies |
| Next.js | `next` in package.json dependencies |
| Nuxt | `nuxt` in package.json dependencies |
| Tailwind | `tailwindcss` in devDependencies |
| Shadcn | `@radix-ui/*` packages or `components.json` exists |
| CSS Modules | `*.module.css` files in src/ |

## Priority Order for Modifications

1. **CSS Variables file** (`globals.css`, `variables.css`, `main.css`)
2. **Tailwind config** (`tailwind.config.js`, `tailwind.config.ts`)
3. **Theme config** (`components.json` for Shadcn)
4. **Component styles** (in order of dependency)
5. **Page styles** (leaf components last)
