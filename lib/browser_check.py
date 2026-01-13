"""
Browser Check Module
====================

Functions to check and install Playwright browsers before agent runs.

This prevents the agent from hanging indefinitely when:
- Chrome is not found at expected path
- browser_install tool takes too long to download

Usage:
    from lib.browser_check import check_playwright_browser, install_playwright_browser

    is_ok, msg = check_playwright_browser()
    if not is_ok:
        success, install_msg = install_playwright_browser(timeout=300)
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def check_playwright_browser() -> Tuple[bool, str]:
    """
    Check if Playwright Chromium browser is installed.

    Uses npx playwright to check browser availability without importing
    playwright directly (avoids dependency on playwright Python package).

    Returns:
        Tuple of (is_installed, message)
    """
    try:
        # Use npx playwright to check if browsers are installed
        # This matches how the MCP server uses playwright
        result = subprocess.run(
            ["npx", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # If dry-run succeeds without errors, browser should be available
        if result.returncode == 0:
            # Check if output indicates browser is already installed
            if "already installed" in result.stdout.lower() or result.stdout.strip() == "":
                return True, "Playwright Chromium browser is available"

        # Try alternative check - see if chromium executable exists
        result2 = subprocess.run(
            ["npx", "playwright", "install", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result2.returncode == 0:
            # Playwright is available, check browsers list
            result3 = subprocess.run(
                ["npx", "@playwright/mcp@latest", "--help"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result3.returncode == 0:
                return True, "Playwright MCP is available"

        return False, f"Browser check indicates installation needed: {result.stderr or result.stdout}"

    except subprocess.TimeoutExpired:
        logger.warning("Browser check timed out after 30 seconds")
        return False, "Browser check timed out - may need installation"

    except FileNotFoundError:
        logger.error("npx not found - Node.js may not be installed")
        return False, "npx not found - please install Node.js"

    except Exception as e:
        logger.error(f"Browser check failed: {e}")
        return False, f"Browser check failed: {str(e)}"


def install_playwright_browser(timeout: int = 300) -> Tuple[bool, str]:
    """
    Install Playwright Chromium browser with timeout.

    Downloads and installs Chromium browser (~100MB+).
    Uses subprocess with timeout to prevent hanging.

    Args:
        timeout: Maximum seconds to wait for installation (default 5 minutes)

    Returns:
        Tuple of (success, message)
    """
    try:
        logger.info(f"Installing Playwright Chromium browser (timeout: {timeout}s)")
        print(f"   Downloading Chromium browser (this may take a few minutes)...")

        result = subprocess.run(
            ["npx", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0:
            logger.info("Playwright Chromium installed successfully")
            return True, "Browser installed successfully"

        error_msg = result.stderr or result.stdout
        logger.error(f"Browser installation failed: {error_msg}")
        return False, f"Installation failed: {error_msg[:200]}"

    except subprocess.TimeoutExpired:
        logger.error(f"Browser installation timed out after {timeout} seconds")
        return False, f"Installation timed out after {timeout}s - check network connection"

    except FileNotFoundError:
        logger.error("npx not found - Node.js may not be installed")
        return False, "npx not found - please install Node.js"

    except Exception as e:
        logger.error(f"Browser installation failed: {e}")
        return False, f"Installation failed: {str(e)}"


def ensure_browser_available(timeout: int = 300) -> Tuple[bool, bool, str]:
    """
    Ensure Playwright browser is available, installing if needed.

    Convenience function that combines check and install.

    Args:
        timeout: Maximum seconds to wait for installation

    Returns:
        Tuple of (is_available, was_installed, message)
    """
    # First check if browser is already available
    is_installed, check_msg = check_playwright_browser()

    if is_installed:
        return True, False, check_msg

    # Try to install
    print("\n" + "=" * 60)
    print("  BROWSER INSTALLATION REQUIRED")
    print("=" * 60)
    print(f"\n{check_msg}")
    print("\nAttempting to install Playwright Chromium browser...")

    success, install_msg = install_playwright_browser(timeout)

    if success:
        print(f"\n{install_msg}")
        print("=" * 60 + "\n")
        return True, True, install_msg

    print(f"\n{install_msg}")
    print("\nBrowser automation will be disabled (YOLO mode)")
    print("=" * 60 + "\n")
    return False, False, install_msg
