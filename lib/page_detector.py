"""
Page Detector
=============

Scans a project and detects pages/routes based on the frontend framework's
routing conventions.

Supported frameworks:
- Next.js Pages Router: /pages/**/*.tsx -> routes
- Next.js App Router: /app/**/page.tsx -> routes
- React Router: parses Route components from code
- Remix: /app/routes/**/*.tsx
- Vue Router: parses routes configuration

This is used by the Component Reference System to suggest which pages
need reference uploads and to auto-match features to page references.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DetectedPage:
    """Information about a detected page/route in the project."""

    element_type: str  # "page", "layout", "component"
    file_path: str  # Relative path from project root
    route: Optional[str]  # Computed route (e.g., "/dashboard")
    element_name: str  # Component/page name
    framework_type: str  # "nextjs-pages", "nextjs-app", "react-router", etc.

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "element_type": self.element_type,
            "file_path": self.file_path,
            "route": self.route,
            "element_name": self.element_name,
            "framework_type": self.framework_type,
        }


@dataclass
class PageDetectionResult:
    """Result of scanning a project for pages."""

    framework_type: str
    pages: List[DetectedPage] = field(default_factory=list)
    layouts: List[DetectedPage] = field(default_factory=list)
    components: List[DetectedPage] = field(default_factory=list)

    def all_elements(self) -> List[DetectedPage]:
        """Return all detected elements."""
        return self.pages + self.layouts + self.components

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "framework_type": self.framework_type,
            "pages": [p.to_dict() for p in self.pages],
            "layouts": [l.to_dict() for l in self.layouts],
            "components": [c.to_dict() for c in self.components],
            "total_pages": len(self.pages),
            "total_layouts": len(self.layouts),
        }


class PageDetector:
    """
    Detects pages and routes from project structure.

    Analyzes the project to identify:
    - Which routing framework is used
    - All pages and their routes
    - Layout components
    - Key UI components

    Usage:
        detector = PageDetector()
        result = detector.scan(project_dir)
        for page in result.pages:
            print(page.route, page.file_path)
    """

    # File patterns to skip
    SKIP_PATTERNS = [
        "__tests__",
        ".test.",
        ".spec.",
        "node_modules",
        ".next",
        ".nuxt",
        "dist",
        "build",
    ]

    def __init__(self):
        """Initialize the page detector."""
        pass

    def detect_framework_routing(self, project_dir: Path) -> str:
        """
        Detect which routing framework/pattern is used.

        Args:
            project_dir: Root directory of the project

        Returns:
            Framework routing type identifier
        """
        # Check for Next.js App Router
        app_dir = project_dir / "app"
        src_app_dir = project_dir / "src" / "app"
        if (app_dir.exists() and (app_dir / "page.tsx").exists()) or \
           (app_dir.exists() and (app_dir / "page.jsx").exists()) or \
           (src_app_dir.exists() and (src_app_dir / "page.tsx").exists()):
            return "nextjs-app"

        # Check for Next.js Pages Router
        pages_dir = project_dir / "pages"
        src_pages_dir = project_dir / "src" / "pages"
        if pages_dir.exists() or src_pages_dir.exists():
            return "nextjs-pages"

        # Check for Remix
        remix_routes = project_dir / "app" / "routes"
        if remix_routes.exists():
            return "remix"

        # Check for Vue Router (look for router config)
        for pattern in ["**/router/**/*.ts", "**/router/**/*.js", "**/router.ts", "**/router.js"]:
            if list(project_dir.glob(pattern)):
                return "vue-router"

        # Check for React Router (look for Route imports in src)
        src_dir = project_dir / "src"
        if src_dir.exists():
            for tsx_file in src_dir.glob("**/*.tsx"):
                try:
                    content = tsx_file.read_text(encoding="utf-8")
                    if "react-router" in content or "Route " in content:
                        return "react-router"
                except Exception:
                    continue

        return "unknown"

    def scan(self, project_dir: Path) -> PageDetectionResult:
        """
        Scan project and detect all pages.

        Args:
            project_dir: Root directory of the project

        Returns:
            PageDetectionResult with detected pages and layouts
        """
        framework_type = self.detect_framework_routing(project_dir)

        if framework_type == "nextjs-app":
            return self._scan_nextjs_app_router(project_dir, framework_type)
        elif framework_type == "nextjs-pages":
            return self._scan_nextjs_pages_router(project_dir, framework_type)
        elif framework_type == "remix":
            return self._scan_remix(project_dir, framework_type)
        elif framework_type == "react-router":
            return self._scan_react_router(project_dir, framework_type)
        elif framework_type == "vue-router":
            return self._scan_vue_router(project_dir, framework_type)
        else:
            # Fallback: scan for common component patterns
            return self._scan_generic(project_dir, framework_type)

    def _scan_nextjs_app_router(self, project_dir: Path, framework_type: str) -> PageDetectionResult:
        """Scan Next.js App Router structure."""
        result = PageDetectionResult(framework_type=framework_type)

        # Check both /app and /src/app
        app_dirs = [
            project_dir / "app",
            project_dir / "src" / "app",
        ]

        for app_dir in app_dirs:
            if not app_dir.exists():
                continue

            # Find all page.tsx/page.jsx files
            for page_file in app_dir.glob("**/page.tsx"):
                if self._should_skip(page_file):
                    continue

                route = self._app_router_path_to_route(page_file, app_dir)
                name = self._extract_page_name(route)

                result.pages.append(DetectedPage(
                    element_type="page",
                    file_path=str(page_file.relative_to(project_dir)),
                    route=route,
                    element_name=name,
                    framework_type=framework_type,
                ))

            for page_file in app_dir.glob("**/page.jsx"):
                if self._should_skip(page_file):
                    continue

                route = self._app_router_path_to_route(page_file, app_dir)
                name = self._extract_page_name(route)

                result.pages.append(DetectedPage(
                    element_type="page",
                    file_path=str(page_file.relative_to(project_dir)),
                    route=route,
                    element_name=name,
                    framework_type=framework_type,
                ))

            # Find all layout.tsx files
            for layout_file in app_dir.glob("**/layout.tsx"):
                if self._should_skip(layout_file):
                    continue

                route = self._app_router_path_to_route(layout_file, app_dir)
                name = f"Layout ({route})" if route != "/" else "Root Layout"

                result.layouts.append(DetectedPage(
                    element_type="layout",
                    file_path=str(layout_file.relative_to(project_dir)),
                    route=route,
                    element_name=name,
                    framework_type=framework_type,
                ))

        return result

    def _scan_nextjs_pages_router(self, project_dir: Path, framework_type: str) -> PageDetectionResult:
        """Scan Next.js Pages Router structure."""
        result = PageDetectionResult(framework_type=framework_type)

        # Check both /pages and /src/pages
        pages_dirs = [
            project_dir / "pages",
            project_dir / "src" / "pages",
        ]

        for pages_dir in pages_dirs:
            if not pages_dir.exists():
                continue

            # Find all .tsx/.jsx files in pages
            for page_file in pages_dir.glob("**/*.tsx"):
                if self._should_skip(page_file):
                    continue

                # Skip _app, _document, _error, api routes
                filename = page_file.stem
                if filename.startswith("_") or "api" in str(page_file.relative_to(pages_dir)):
                    continue

                route = self._pages_router_path_to_route(page_file, pages_dir)
                name = self._extract_page_name(route)

                result.pages.append(DetectedPage(
                    element_type="page",
                    file_path=str(page_file.relative_to(project_dir)),
                    route=route,
                    element_name=name,
                    framework_type=framework_type,
                ))

            for page_file in pages_dir.glob("**/*.jsx"):
                if self._should_skip(page_file):
                    continue

                filename = page_file.stem
                if filename.startswith("_") or "api" in str(page_file.relative_to(pages_dir)):
                    continue

                route = self._pages_router_path_to_route(page_file, pages_dir)
                name = self._extract_page_name(route)

                result.pages.append(DetectedPage(
                    element_type="page",
                    file_path=str(page_file.relative_to(project_dir)),
                    route=route,
                    element_name=name,
                    framework_type=framework_type,
                ))

        return result

    def _scan_remix(self, project_dir: Path, framework_type: str) -> PageDetectionResult:
        """Scan Remix routes structure."""
        result = PageDetectionResult(framework_type=framework_type)

        routes_dir = project_dir / "app" / "routes"
        if not routes_dir.exists():
            return result

        for route_file in routes_dir.glob("**/*.tsx"):
            if self._should_skip(route_file):
                continue

            route = self._remix_path_to_route(route_file, routes_dir)
            name = self._extract_page_name(route)

            result.pages.append(DetectedPage(
                element_type="page",
                file_path=str(route_file.relative_to(project_dir)),
                route=route,
                element_name=name,
                framework_type=framework_type,
            ))

        return result

    def _scan_react_router(self, project_dir: Path, framework_type: str) -> PageDetectionResult:
        """Scan React Router configuration."""
        result = PageDetectionResult(framework_type=framework_type)

        src_dir = project_dir / "src"
        if not src_dir.exists():
            return result

        # Look for router configuration files
        router_patterns = [
            "**/routes.tsx",
            "**/routes.jsx",
            "**/router.tsx",
            "**/router.jsx",
            "**/App.tsx",
            "**/App.jsx",
        ]

        for pattern in router_patterns:
            for router_file in src_dir.glob(pattern):
                try:
                    content = router_file.read_text(encoding="utf-8")
                    routes = self._extract_react_router_routes(content)

                    for route in routes:
                        name = self._extract_page_name(route)
                        result.pages.append(DetectedPage(
                            element_type="page",
                            file_path=str(router_file.relative_to(project_dir)),
                            route=route,
                            element_name=name,
                            framework_type=framework_type,
                        ))
                except Exception as e:
                    logger.warning(f"Error parsing {router_file}: {e}")

        return result

    def _scan_vue_router(self, project_dir: Path, framework_type: str) -> PageDetectionResult:
        """Scan Vue Router configuration."""
        result = PageDetectionResult(framework_type=framework_type)

        # Look for router config
        router_patterns = [
            "**/router/**/*.ts",
            "**/router/**/*.js",
            "**/router.ts",
            "**/router.js",
        ]

        for pattern in router_patterns:
            for router_file in project_dir.glob(pattern):
                try:
                    content = router_file.read_text(encoding="utf-8")
                    routes = self._extract_vue_router_routes(content)

                    for route in routes:
                        name = self._extract_page_name(route)
                        result.pages.append(DetectedPage(
                            element_type="page",
                            file_path=str(router_file.relative_to(project_dir)),
                            route=route,
                            element_name=name,
                            framework_type=framework_type,
                        ))
                except Exception as e:
                    logger.warning(f"Error parsing {router_file}: {e}")

        return result

    def _scan_generic(self, project_dir: Path, framework_type: str) -> PageDetectionResult:
        """Generic scan for common component patterns."""
        result = PageDetectionResult(framework_type=framework_type)

        # Look for common page directories
        page_dirs = ["pages", "views", "screens", "routes"]
        src_dir = project_dir / "src"

        for page_dir_name in page_dirs:
            page_dir = src_dir / page_dir_name if src_dir.exists() else project_dir / page_dir_name
            if not page_dir.exists():
                continue

            for page_file in page_dir.glob("**/*.tsx"):
                if self._should_skip(page_file):
                    continue

                name = page_file.stem
                route = f"/{name.lower()}" if name.lower() != "index" else "/"

                result.pages.append(DetectedPage(
                    element_type="page",
                    file_path=str(page_file.relative_to(project_dir)),
                    route=route,
                    element_name=name,
                    framework_type=framework_type,
                ))

        return result

    def _should_skip(self, file_path: Path) -> bool:
        """Check if a file should be skipped."""
        path_str = str(file_path)
        return any(pattern in path_str for pattern in self.SKIP_PATTERNS)

    def _app_router_path_to_route(self, file_path: Path, app_dir: Path) -> str:
        """Convert App Router file path to route."""
        # Get path relative to app dir
        rel_path = file_path.relative_to(app_dir)

        # Remove page.tsx/layout.tsx
        route_parts = list(rel_path.parts[:-1])

        # Filter out route groups (directories starting with parentheses)
        route_parts = [p for p in route_parts if not p.startswith("(")]

        # Handle dynamic segments [param] -> :param
        route_parts = [
            f":{p[1:-1]}" if p.startswith("[") and p.endswith("]") else p
            for p in route_parts
        ]

        route = "/" + "/".join(route_parts)
        return route if route != "/" else "/"

    def _pages_router_path_to_route(self, file_path: Path, pages_dir: Path) -> str:
        """Convert Pages Router file path to route."""
        rel_path = file_path.relative_to(pages_dir)

        # Build route from path
        route_parts = []
        for part in rel_path.parts:
            if part.endswith(".tsx") or part.endswith(".jsx"):
                part = part.rsplit(".", 1)[0]  # Remove extension
                if part != "index":
                    route_parts.append(part)
            else:
                route_parts.append(part)

        # Handle dynamic segments [param] -> :param
        route_parts = [
            f":{p[1:-1]}" if p.startswith("[") and p.endswith("]") else p
            for p in route_parts
        ]

        route = "/" + "/".join(route_parts)
        return route if route else "/"

    def _remix_path_to_route(self, file_path: Path, routes_dir: Path) -> str:
        """Convert Remix route file path to route."""
        rel_path = file_path.relative_to(routes_dir)
        filename = rel_path.stem

        # Remix uses . for nested routes and $ for dynamic segments
        route = filename.replace(".", "/").replace("$", ":")

        if route == "_index" or route == "index":
            return "/"

        return f"/{route}"

    def _extract_react_router_routes(self, content: str) -> List[str]:
        """Extract routes from React Router JSX."""
        routes = []

        # Match <Route path="/something" ...>
        route_pattern = r'<Route[^>]*path=["\']([^"\']+)["\']'
        matches = re.findall(route_pattern, content)
        routes.extend(matches)

        # Match path: "/something" in route objects
        obj_pattern = r'path:\s*["\']([^"\']+)["\']'
        matches = re.findall(obj_pattern, content)
        routes.extend(matches)

        return list(set(routes))

    def _extract_vue_router_routes(self, content: str) -> List[str]:
        """Extract routes from Vue Router config."""
        routes = []

        # Match path: '/something'
        pattern = r'path:\s*["\']([^"\']+)["\']'
        matches = re.findall(pattern, content)
        routes.extend(matches)

        return list(set(routes))

    def _extract_page_name(self, route: str) -> str:
        """Extract a readable page name from route."""
        if route == "/":
            return "Home"

        # Get last segment
        segments = [s for s in route.split("/") if s and not s.startswith(":")]
        if not segments:
            return "Dynamic Page"

        name = segments[-1]
        # Convert kebab-case to Title Case
        return " ".join(word.capitalize() for word in name.replace("-", " ").replace("_", " ").split())


def detect_project_pages(project_dir: Path) -> PageDetectionResult:
    """
    Convenience function to scan a project for pages.

    Args:
        project_dir: Root directory of the project

    Returns:
        PageDetectionResult with detected pages
    """
    detector = PageDetector()
    return detector.scan(project_dir)


def match_feature_to_page_reference(
    feature_category: str,
    feature_name: str,
    feature_description: str,
    page_references: List[dict],
) -> Optional[dict]:
    """
    Match a feature to the most appropriate page reference.

    Uses keyword matching to find the best page reference for a feature.

    Args:
        feature_category: Feature category (e.g., "Dashboard UI")
        feature_name: Feature name
        feature_description: Feature description
        page_references: List of PageReference dicts

    Returns:
        Best matching PageReference dict or None
    """
    if not page_references:
        return None

    # Combine feature text for matching
    feature_text = f"{feature_category} {feature_name} {feature_description}".lower()

    best_match = None
    best_score = 0

    for ref in page_references:
        if not ref.get("auto_match_enabled", True):
            continue

        score = 0

        # Check page identifier
        page_id = ref.get("page_identifier", "").lower().strip("/")
        if page_id and page_id in feature_text:
            score += 10

        # Check display name
        display_name = ref.get("display_name", "").lower()
        if display_name and display_name in feature_text:
            score += 5

        # Check keywords
        keywords = ref.get("match_keywords", []) or []
        for keyword in keywords:
            if keyword.lower() in feature_text:
                score += 3

        if score > best_score:
            best_score = score
            best_match = ref

    return best_match if best_score > 0 else None
