"""
Screenshot Service
==================

Provides screenshot capabilities using Playwright for capturing
web pages and visual comparison during redesign operations.

Features:
- Capture full page screenshots from URLs
- Capture specific element screenshots
- Compare before/after screenshots
- Generate visual diff highlights
"""

import asyncio
import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Screenshot functionality will be limited.")


class ScreenshotService:
    """
    Service for capturing screenshots of web pages using Playwright.

    This service manages a browser instance and provides methods for
    capturing screenshots of URLs for design reference extraction.
    """

    def __init__(self):
        """Initialize the screenshot service."""
        self._browser: Optional["Browser"] = None
        self._playwright = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self) -> "Browser":
        """Ensure browser is started and return it."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
            )

        async with self._lock:
            if self._browser is None:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ]
                )
                logger.info("Playwright browser started")

            return self._browser

    async def close(self) -> None:
        """Close the browser instance."""
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
                logger.info("Playwright browser closed")

    async def capture_url(
        self,
        url: str,
        width: int = 1920,
        height: int = 1080,
        full_page: bool = True,
        wait_for_load: bool = True,
        timeout_ms: int = 30000,
    ) -> bytes:
        """
        Capture a screenshot of a URL.

        Args:
            url: The URL to capture
            width: Viewport width in pixels
            height: Viewport height in pixels
            full_page: Whether to capture the full page or just viewport
            wait_for_load: Whether to wait for network idle
            timeout_ms: Timeout for page load in milliseconds

        Returns:
            PNG screenshot data as bytes
        """
        browser = await self._ensure_browser()
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=2,  # Retina quality
        )

        try:
            page = await context.new_page()

            # Navigate to URL
            await page.goto(
                url,
                wait_until="networkidle" if wait_for_load else "domcontentloaded",
                timeout=timeout_ms,
            )

            # Wait a bit for any animations to settle
            await page.wait_for_timeout(500)

            # Take screenshot
            screenshot = await page.screenshot(
                full_page=full_page,
                type="png",
            )

            logger.info(f"Captured screenshot of {url} ({len(screenshot)} bytes)")
            return screenshot

        finally:
            await context.close()

    async def capture_url_as_base64(
        self,
        url: str,
        width: int = 1920,
        height: int = 1080,
        full_page: bool = True,
    ) -> str:
        """
        Capture a screenshot and return as base64 string.

        Args:
            url: The URL to capture
            width: Viewport width
            height: Viewport height
            full_page: Whether to capture full page

        Returns:
            Base64-encoded PNG screenshot
        """
        screenshot = await self.capture_url(url, width, height, full_page)
        return base64.b64encode(screenshot).decode("utf-8")

    async def capture_element(
        self,
        url: str,
        selector: str,
        padding: int = 10,
        timeout_ms: int = 30000,
    ) -> bytes:
        """
        Capture a screenshot of a specific element.

        Args:
            url: The URL to navigate to
            selector: CSS selector for the element
            padding: Padding around the element in pixels
            timeout_ms: Timeout for page load

        Returns:
            PNG screenshot data as bytes
        """
        browser = await self._ensure_browser()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
        )

        try:
            page = await context.new_page()

            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            await page.wait_for_timeout(500)

            # Find element
            element = await page.wait_for_selector(selector, timeout=10000)
            if not element:
                raise ValueError(f"Element not found: {selector}")

            # Screenshot the element
            screenshot = await element.screenshot(type="png")

            logger.info(f"Captured element {selector} from {url}")
            return screenshot

        finally:
            await context.close()

    async def capture_multiple_viewports(
        self,
        url: str,
        viewports: Optional[list[dict]] = None,
    ) -> dict[str, bytes]:
        """
        Capture screenshots at multiple viewport sizes.

        Args:
            url: The URL to capture
            viewports: List of viewport configs [{name, width, height}]
                      Default: mobile, tablet, desktop

        Returns:
            Dictionary mapping viewport name to screenshot bytes
        """
        if viewports is None:
            viewports = [
                {"name": "mobile", "width": 375, "height": 812},
                {"name": "tablet", "width": 768, "height": 1024},
                {"name": "desktop", "width": 1920, "height": 1080},
            ]

        results = {}
        for viewport in viewports:
            screenshot = await self.capture_url(
                url,
                width=viewport["width"],
                height=viewport["height"],
                full_page=True,
            )
            results[viewport["name"]] = screenshot

        return results

    async def compare_screenshots(
        self,
        before: bytes,
        after: bytes,
        threshold: float = 0.1,
    ) -> dict:
        """
        Compare two screenshots and calculate difference.

        Args:
            before: PNG bytes of before screenshot
            after: PNG bytes of after screenshot
            threshold: Sensitivity threshold (0-1)

        Returns:
            Dictionary with comparison results:
            - different: bool - whether images are different
            - difference_percentage: float - percentage of changed pixels
            - diff_image: Optional[bytes] - visual diff image if different
        """
        try:
            from PIL import Image
            import io
        except ImportError:
            logger.warning("Pillow not installed. Cannot compare screenshots.")
            return {
                "different": True,
                "difference_percentage": -1,
                "diff_image": None,
                "error": "Pillow not installed"
            }

        # Load images
        img1 = Image.open(io.BytesIO(before)).convert("RGBA")
        img2 = Image.open(io.BytesIO(after)).convert("RGBA")

        # Resize to same dimensions if needed
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)

        # Calculate pixel difference
        width, height = img1.size
        total_pixels = width * height
        different_pixels = 0

        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        # Create diff image
        diff_data = []

        for p1, p2 in zip(pixels1, pixels2):
            # Calculate color difference
            diff = sum(abs(a - b) for a, b in zip(p1[:3], p2[:3])) / (255 * 3)

            if diff > threshold:
                different_pixels += 1
                # Highlight difference in red
                diff_data.append((255, 0, 0, 200))
            else:
                # Keep original with reduced opacity
                diff_data.append((p2[0], p2[1], p2[2], 100))

        difference_percentage = (different_pixels / total_pixels) * 100
        is_different = difference_percentage > 1.0  # More than 1% different

        # Create diff image
        diff_image = None
        if is_different:
            diff_img = Image.new("RGBA", img1.size)
            diff_img.putdata(diff_data)

            # Composite diff over after image
            result = Image.alpha_composite(img2, diff_img)

            buffer = io.BytesIO()
            result.save(buffer, format="PNG")
            diff_image = buffer.getvalue()

        return {
            "different": is_different,
            "difference_percentage": round(difference_percentage, 2),
            "diff_image": diff_image,
            "before_size": img1.size,
            "after_size": img2.size,
        }

    async def save_screenshot(
        self,
        screenshot: bytes,
        path: Path,
    ) -> Path:
        """
        Save screenshot to a file.

        Args:
            screenshot: PNG bytes
            path: Destination path

        Returns:
            Path where screenshot was saved
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(screenshot)
        logger.info(f"Screenshot saved to {path}")
        return path


# Singleton instance
_screenshot_service: Optional[ScreenshotService] = None


def get_screenshot_service() -> ScreenshotService:
    """Get the singleton screenshot service instance."""
    global _screenshot_service
    if _screenshot_service is None:
        _screenshot_service = ScreenshotService()
    return _screenshot_service


async def cleanup_screenshot_service() -> None:
    """Cleanup the screenshot service on shutdown."""
    global _screenshot_service
    if _screenshot_service is not None:
        await _screenshot_service.close()
        _screenshot_service = None
