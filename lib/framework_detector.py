"""
Framework Detector
==================

Detects the frontend framework, styling approach, and UI library
used in a project by analyzing package.json and file structure.

This information is used by the redesign system to generate
appropriate output formats (Tailwind config, CSS variables, etc.).
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FrameworkInfo:
    """Information about detected frontend framework and styling."""

    # Core framework (react, vue, svelte, angular, next, nuxt)
    framework: str

    # Styling approach (tailwind, css-modules, styled-components, css-variables, scss)
    styling: str

    # UI library if any (shadcn, radix, mui, chakra, ant-design, none)
    ui_library: Optional[str]

    # Additional detected features
    typescript: bool = False
    vite: bool = False
    webpack: bool = False

    # Paths to key files
    tailwind_config_path: Optional[Path] = None
    globals_css_path: Optional[Path] = None
    theme_config_path: Optional[Path] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "framework": self.framework,
            "styling": self.styling,
            "ui_library": self.ui_library,
            "typescript": self.typescript,
            "vite": self.vite,
            "webpack": self.webpack,
            "tailwind_config_path": str(self.tailwind_config_path) if self.tailwind_config_path else None,
            "globals_css_path": str(self.globals_css_path) if self.globals_css_path else None,
            "theme_config_path": str(self.theme_config_path) if self.theme_config_path else None,
        }

    @property
    def identifier(self) -> str:
        """Generate a unique identifier for this framework combination."""
        parts = [self.framework, self.styling]
        if self.ui_library:
            parts.append(self.ui_library)
        return "-".join(parts)


class FrameworkDetector:
    """
    Detects frontend framework and styling from project structure.

    Usage:
        detector = FrameworkDetector()
        info = detector.detect(project_dir)
        print(info.framework, info.styling, info.ui_library)
    """

    def __init__(self):
        """Initialize the framework detector."""
        pass

    def detect(self, project_dir: Path) -> FrameworkInfo:
        """
        Detect framework, styling, and UI library for a project.

        Args:
            project_dir: Root directory of the project

        Returns:
            FrameworkInfo with detected configuration
        """
        # Read package.json
        pkg = self._read_package_json(project_dir)

        # Detect core framework
        framework = self._detect_framework(pkg)

        # Detect styling approach
        styling = self._detect_styling(pkg, project_dir)

        # Detect UI library
        ui_library = self._detect_ui_library(pkg, project_dir)

        # Detect additional features
        typescript = self._has_typescript(pkg, project_dir)
        vite = self._has_vite(pkg)
        webpack = self._has_webpack(pkg)

        # Find key file paths
        tailwind_config_path = self._find_tailwind_config(project_dir)
        globals_css_path = self._find_globals_css(project_dir)
        theme_config_path = self._find_theme_config(project_dir, ui_library)

        info = FrameworkInfo(
            framework=framework,
            styling=styling,
            ui_library=ui_library,
            typescript=typescript,
            vite=vite,
            webpack=webpack,
            tailwind_config_path=tailwind_config_path,
            globals_css_path=globals_css_path,
            theme_config_path=theme_config_path,
        )

        logger.info(f"Detected framework: {info.identifier}")
        return info

    def _read_package_json(self, project_dir: Path) -> dict:
        """Read and parse package.json."""
        pkg_path = project_dir / "package.json"

        if not pkg_path.exists():
            logger.warning(f"No package.json found in {project_dir}")
            return {"dependencies": {}, "devDependencies": {}}

        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error reading package.json: {e}")
            return {"dependencies": {}, "devDependencies": {}}

    def _detect_framework(self, pkg: dict) -> str:
        """Detect the core frontend framework."""
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        # Check for meta-frameworks first
        if "next" in deps:
            return "next"
        if "nuxt" in deps:
            return "nuxt"
        if "remix" in deps or "@remix-run/react" in deps:
            return "remix"
        if "astro" in deps:
            return "astro"

        # Check for core frameworks
        if "react" in deps or "react-dom" in deps:
            return "react"
        if "vue" in deps:
            return "vue"
        if "svelte" in deps:
            return "svelte"
        if "@angular/core" in deps:
            return "angular"
        if "solid-js" in deps:
            return "solid"
        if "preact" in deps:
            return "preact"

        return "unknown"

    def _detect_styling(self, pkg: dict, project_dir: Path) -> str:
        """Detect the styling approach."""
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        # Check for Tailwind CSS (most common with modern projects)
        if "tailwindcss" in deps:
            return "tailwind"

        # Check for CSS-in-JS solutions
        if "styled-components" in deps:
            return "styled-components"
        if "@emotion/react" in deps or "@emotion/styled" in deps:
            return "emotion"
        if "styled-jsx" in deps:
            return "styled-jsx"

        # Check for preprocessors
        if "sass" in deps or "node-sass" in deps:
            return "scss"
        if "less" in deps:
            return "less"

        # Check for CSS modules (by file pattern)
        src_dir = project_dir / "src"
        if src_dir.exists():
            css_modules = list(src_dir.glob("**/*.module.css"))
            if css_modules:
                return "css-modules"

        # Default to CSS variables (native CSS)
        return "css-variables"

    def _detect_ui_library(self, pkg: dict, project_dir: Path) -> Optional[str]:
        """Detect UI component library."""
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        # Check for shadcn (uses Radix UI primitives)
        if "@radix-ui/react-slot" in deps:
            # Check for components.json which indicates shadcn
            if (project_dir / "components.json").exists():
                return "shadcn"
            # Could still be using Radix directly
            return "radix"

        # Check for other UI libraries
        if "@mui/material" in deps or "@material-ui/core" in deps:
            return "mui"
        if "@chakra-ui/react" in deps:
            return "chakra"
        if "antd" in deps:
            return "ant-design"
        if "@mantine/core" in deps:
            return "mantine"
        if "primereact" in deps:
            return "primereact"
        if "@headlessui/react" in deps:
            return "headlessui"
        if "daisyui" in deps:
            return "daisyui"

        return None

    def _has_typescript(self, pkg: dict, project_dir: Path) -> bool:
        """Check if project uses TypeScript."""
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        if "typescript" in deps:
            return True

        # Check for tsconfig
        return (project_dir / "tsconfig.json").exists()

    def _has_vite(self, pkg: dict) -> bool:
        """Check if project uses Vite."""
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        return "vite" in deps

    def _has_webpack(self, pkg: dict) -> bool:
        """Check if project uses Webpack."""
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        return "webpack" in deps or "webpack-cli" in deps

    def _find_tailwind_config(self, project_dir: Path) -> Optional[Path]:
        """Find Tailwind config file."""
        candidates = [
            "tailwind.config.ts",
            "tailwind.config.js",
            "tailwind.config.mjs",
            "tailwind.config.cjs",
        ]

        for name in candidates:
            path = project_dir / name
            if path.exists():
                return path

        return None

    def _find_globals_css(self, project_dir: Path) -> Optional[Path]:
        """Find global CSS file."""
        candidates = [
            # Common locations
            "src/styles/globals.css",
            "src/styles/global.css",
            "src/styles/main.css",
            "src/styles/index.css",
            "src/globals.css",
            "src/index.css",
            "src/App.css",
            "styles/globals.css",
            "styles/global.css",
            "app/globals.css",  # Next.js app router
            # Vue common
            "src/assets/main.css",
            "src/assets/styles/main.css",
        ]

        for name in candidates:
            path = project_dir / name
            if path.exists():
                return path

        # Search for any CSS file in src/styles
        styles_dir = project_dir / "src" / "styles"
        if styles_dir.exists():
            css_files = list(styles_dir.glob("*.css"))
            if css_files:
                return css_files[0]

        return None

    def _find_theme_config(self, project_dir: Path, ui_library: Optional[str]) -> Optional[Path]:
        """Find theme configuration file based on UI library."""
        if ui_library == "shadcn":
            path = project_dir / "components.json"
            if path.exists():
                return path

        if ui_library == "chakra":
            candidates = [
                "src/theme.ts",
                "src/theme/index.ts",
                "src/styles/theme.ts",
                "theme.ts",
            ]
            for name in candidates:
                path = project_dir / name
                if path.exists():
                    return path

        if ui_library == "mui":
            candidates = [
                "src/theme.ts",
                "src/theme/index.ts",
                "src/theme.js",
            ]
            for name in candidates:
                path = project_dir / name
                if path.exists():
                    return path

        return None


# Convenience function
def detect_framework(project_dir: Path) -> FrameworkInfo:
    """
    Convenience function to detect framework for a project.

    Args:
        project_dir: Root directory of the project

    Returns:
        FrameworkInfo with detected configuration
    """
    detector = FrameworkDetector()
    return detector.detect(project_dir)


def get_output_format(info: FrameworkInfo) -> str:
    """
    Determine the appropriate output format based on framework info.

    Returns one of:
    - "tailwind-config": Generate tailwind.config.js
    - "tailwind-css-vars": Generate tailwind.config.js with CSS variables
    - "css-variables": Generate pure CSS variables
    - "shadcn": Generate shadcn theme format
    """
    if info.ui_library == "shadcn":
        return "shadcn"

    if info.styling == "tailwind":
        # For Tailwind, prefer CSS variables approach for flexibility
        return "tailwind-css-vars"

    if info.styling in ("css-modules", "css-variables", "scss"):
        return "css-variables"

    if info.styling in ("styled-components", "emotion"):
        return "css-variables"  # They can consume CSS vars

    return "css-variables"  # Default fallback
