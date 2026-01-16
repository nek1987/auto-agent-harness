"""
Browser Check Module
====================

Functions to check and install agent-browser before agent runs.

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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def check_playwright_browser() -> Tuple[bool, str]:
    """
    Check if agent-browser is available.

    Uses agent-browser CLI to verify availability without importing
    Playwright directly.

    Returns:
        Tuple of (is_installed, message)
    """
    try:
        result = subprocess.run(
            ["agent-browser", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "agent-browser is available"

        return False, f"agent-browser check failed: {result.stderr or result.stdout}"

    except subprocess.TimeoutExpired:
        logger.warning("Browser check timed out after 30 seconds")
        return False, "Browser check timed out - may need installation"

    except FileNotFoundError:
        logger.error("agent-browser not found - please install it")
        if shutil.which("npm"):
            return False, "agent-browser not found - run: npm install -g agent-browser"
        return False, "agent-browser not found and npm unavailable"

    except Exception as e:
        logger.error(f"Browser check failed: {e}")
        return False, f"Browser check failed: {str(e)}"


def install_playwright_browser(timeout: int = 300) -> Tuple[bool, str]:
    """
    Install agent-browser (and Chromium) with timeout.

    Downloads and installs Chromium browser (~100MB+).
    Uses subprocess with timeout to prevent hanging.

    Args:
        timeout: Maximum seconds to wait for installation (default 5 minutes)

    Returns:
        Tuple of (success, message)
    """
    try:
        logger.info(f"Installing agent-browser (timeout: {timeout}s)")
        print("   Installing agent-browser and downloading Chromium (may take a few minutes)...")

        try:
            result = subprocess.run(
                ["agent-browser", "install"],
                capture_output=True,
                text=True,
                timeout=timeout
            )
        except FileNotFoundError:
            if not shutil.which("npm"):
                logger.error("npm not found - cannot install agent-browser")
                return False, "npm not found - please install Node.js"

            logger.info("agent-browser CLI missing - installing globally via npm")
            install_cli = subprocess.run(
                ["npm", "install", "-g", "agent-browser"],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if install_cli.returncode != 0:
                error_msg = install_cli.stderr or install_cli.stdout
                logger.error(f"agent-browser CLI install failed: {error_msg}")
                return False, f"CLI install failed: {error_msg[:200]}"

            result = subprocess.run(
                ["agent-browser", "install"],
                capture_output=True,
                text=True,
                timeout=timeout
            )

        if result.returncode == 0:
            logger.info("agent-browser installed successfully")
            return True, "Browser installed successfully"

        error_msg = result.stderr or result.stdout
        logger.error(f"Browser installation failed: {error_msg}")
        return False, f"Installation failed: {error_msg[:200]}"

    except subprocess.TimeoutExpired:
        logger.error(f"Browser installation timed out after {timeout} seconds")
        return False, f"Installation timed out after {timeout}s - check network connection"

    except FileNotFoundError:
        logger.error("agent-browser not found - please install it")
        return False, "agent-browser not found - install with: npm install -g agent-browser"

    except Exception as e:
        logger.error(f"Browser installation failed: {e}")
        return False, f"Installation failed: {str(e)}"


def ensure_browser_available(timeout: int = 300) -> Tuple[bool, bool, str]:
    """
    Ensure agent-browser is available, installing if needed.

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
    print("\nAttempting to install agent-browser...")

    success, install_msg = install_playwright_browser(timeout)

    if success:
        print(f"\n{install_msg}")
        print("=" * 60 + "\n")
        return True, True, install_msg

    print(f"\n{install_msg}")
    print("\nBrowser automation will be disabled (YOLO mode)")
    print("=" * 60 + "\n")
    return False, False, install_msg
