"""
Error Classification Library
=============================

Provides utilities for:
- Detecting abort/cancellation errors
- Detecting authentication errors
- Detecting rate limit and quota exhaustion errors
- Classifying errors by type
- Generating user-friendly error messages

Ported from automaker/libs/utils/src/error-handler.ts
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Error type classification."""
    AUTHENTICATION = "authentication"
    CANCELLATION = "cancellation"
    ABORT = "abort"
    EXECUTION = "execution"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXHAUSTED = "quota_exhausted"
    NETWORK = "network"
    TIMEOUT = "timeout"
    CONTEXT_LENGTH = "context_length"
    BROWSER = "browser"  # Playwright/browser automation errors
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """Classified error information."""
    type: ErrorType
    message: str
    is_abort: bool = False
    is_auth: bool = False
    is_cancellation: bool = False
    is_rate_limit: bool = False
    is_quota_exhausted: bool = False
    is_retryable: bool = False
    retry_after: Optional[int] = None
    original_error: Optional[Any] = None


def is_abort_error(error: Any) -> bool:
    """
    Check if an error is an abort/cancellation error.

    Args:
        error: The error to check

    Returns:
        True if the error is an abort error
    """
    if isinstance(error, Exception):
        error_name = type(error).__name__
        error_message = str(error)
        return error_name == "AbortError" or "abort" in error_message.lower()
    return False


def is_cancellation_error(error_message: str) -> bool:
    """
    Check if an error is a user-initiated cancellation.

    Args:
        error_message: The error message to check

    Returns:
        True if the error is a user-initiated cancellation
    """
    lower_message = error_message.lower()
    return any(word in lower_message for word in [
        "cancelled",
        "canceled",
        "stopped",
        "aborted",
        "interrupted",
    ])


def is_authentication_error(error_message: str) -> bool:
    """
    Check if an error is an authentication/API key error.

    Args:
        error_message: The error message to check

    Returns:
        True if the error is authentication-related
    """
    patterns = [
        "authentication failed",
        "invalid api key",
        "authentication_failed",
        "fix external api key",
        "unauthorized",
        "invalid_api_key",
        "api key is invalid",
        "401",
    ]
    lower_message = error_message.lower()
    return any(pattern in lower_message for pattern in patterns)


def is_rate_limit_error(error: Any) -> bool:
    """
    Check if an error is a rate limit error (429 Too Many Requests).

    Args:
        error: The error to check

    Returns:
        True if the error is a rate limit error
    """
    message = str(error) if error else ""
    lower_message = message.lower()
    return "429" in message or "rate_limit" in lower_message or "rate limit" in lower_message


def is_quota_exhausted_error(error: Any) -> bool:
    """
    Check if an error indicates quota/usage exhaustion.
    This includes session limits, weekly limits, credit/billing issues, and overloaded errors.

    Args:
        error: The error to check

    Returns:
        True if the error indicates quota exhaustion
    """
    message = str(error) if error else ""
    lower_message = message.lower()

    # Check for overloaded/capacity errors
    if any(word in lower_message for word in ["overloaded", "overloaded_error", "capacity"]):
        return True

    # Check for usage/quota limit patterns
    quota_patterns = [
        "limit reached",
        "usage limit",
        "quota exceeded",
        "quota_exceeded",
        "session limit",
        "weekly limit",
        "monthly limit",
        "daily limit",
        "requests per minute",
        "tokens per minute",
    ]
    if any(pattern in lower_message for pattern in quota_patterns):
        return True

    # Check for billing/credit issues
    billing_patterns = [
        "credit balance",
        "insufficient credits",
        "insufficient balance",
        "no credits",
        "out of credits",
        "billing",
        "payment required",
    ]
    if any(pattern in lower_message for pattern in billing_patterns):
        return True

    # Check for upgrade prompts (often indicates limit reached)
    if "/upgrade" in lower_message or "extra-usage" in lower_message:
        return True

    return False


def is_network_error(error: Any) -> bool:
    """
    Check if an error is a network-related error.

    Args:
        error: The error to check

    Returns:
        True if the error is network-related
    """
    message = str(error) if error else ""
    lower_message = message.lower()

    network_patterns = [
        "connection refused",
        "connection reset",
        "connection error",
        "network error",
        "dns",
        "timeout",
        "econnrefused",
        "econnreset",
        "etimedout",
        "unreachable",
        "no internet",
        "offline",
    ]
    return any(pattern in lower_message for pattern in network_patterns)


def is_context_length_error(error: Any) -> bool:
    """
    Check if an error is a context length exceeded error.

    Args:
        error: The error to check

    Returns:
        True if the error is context length related
    """
    message = str(error) if error else ""
    lower_message = message.lower()

    context_patterns = [
        "context length",
        "context_length",
        "max tokens",
        "maximum context",
        "too many tokens",
        "token limit",
    ]
    return any(pattern in lower_message for pattern in context_patterns)


def is_browser_error(error: Any) -> bool:
    """
    Check if an error is a Playwright/browser automation error.

    Args:
        error: The error to check

    Returns:
        True if the error is browser/Playwright related
    """
    message = str(error) if error else ""
    lower_message = message.lower()

    browser_patterns = [
        "playwright",
        "chromium",
        "chrome is not found",
        "browser not found",
        "browser_install",
        "browser_navigate",
        "launchpersistentcontext",
        "browsertype.launch",
        "npx playwright install",
        "mcp__playwright",
    ]
    return any(pattern in lower_message for pattern in browser_patterns)


def extract_retry_after(error: Any) -> Optional[int]:
    """
    Extract retry-after duration from rate limit error.

    Args:
        error: The error to extract retry-after from

    Returns:
        Number of seconds to wait, or None if not found
    """
    message = str(error) if error else ""

    # Try to extract from Retry-After header format
    retry_match = re.search(r"retry[_-]?after[:\s]+(\d+)", message, re.IGNORECASE)
    if retry_match:
        return int(retry_match.group(1))

    # Try to extract from error message patterns
    wait_match = re.search(r"wait[:\s]+(\d+)\s*(?:second|sec|s)", message, re.IGNORECASE)
    if wait_match:
        return int(wait_match.group(1))

    # Try to extract from "try again in X seconds" pattern
    try_again_match = re.search(r"try again in (\d+)\s*(?:second|sec|s)", message, re.IGNORECASE)
    if try_again_match:
        return int(try_again_match.group(1))

    return None


def classify_error(error: Any) -> ErrorInfo:
    """
    Classify an error into a specific type.

    Args:
        error: The error to classify

    Returns:
        Classified error information
    """
    message = str(error) if error else "Unknown error"
    if isinstance(error, Exception):
        message = str(error)

    is_abort = is_abort_error(error)
    is_auth = is_authentication_error(message)
    is_cancellation = is_cancellation_error(message)
    is_rate_limit = is_rate_limit_error(error)
    is_quota = is_quota_exhausted_error(error)
    is_network = is_network_error(error)
    is_context = is_context_length_error(error)
    is_browser = is_browser_error(error)

    retry_after = extract_retry_after(error) if is_rate_limit else None

    # Determine error type (priority order)
    if is_auth:
        error_type = ErrorType.AUTHENTICATION
        is_retryable = False
    elif is_quota:
        # Quota exhaustion takes priority over rate limit since it's more specific
        error_type = ErrorType.QUOTA_EXHAUSTED
        is_retryable = False
    elif is_rate_limit:
        error_type = ErrorType.RATE_LIMIT
        is_retryable = True
    elif is_browser:
        # Browser errors should switch to YOLO mode
        error_type = ErrorType.BROWSER
        is_retryable = False
    elif is_context:
        error_type = ErrorType.CONTEXT_LENGTH
        is_retryable = False
    elif is_network:
        error_type = ErrorType.NETWORK
        is_retryable = True
    elif is_abort:
        error_type = ErrorType.ABORT
        is_retryable = False
    elif is_cancellation:
        error_type = ErrorType.CANCELLATION
        is_retryable = False
    elif isinstance(error, Exception):
        error_type = ErrorType.EXECUTION
        is_retryable = False
    else:
        error_type = ErrorType.UNKNOWN
        is_retryable = False

    return ErrorInfo(
        type=error_type,
        message=message,
        is_abort=is_abort,
        is_auth=is_auth,
        is_cancellation=is_cancellation,
        is_rate_limit=is_rate_limit,
        is_quota_exhausted=is_quota,
        is_retryable=is_retryable,
        retry_after=retry_after if is_rate_limit else None,
        original_error=error,
    )


def get_user_friendly_message(error_info: ErrorInfo) -> str:
    """
    Get a user-friendly error message.

    Args:
        error_info: The classified error info

    Returns:
        User-friendly error message
    """
    if error_info.is_abort:
        return "Operation was cancelled"

    if error_info.is_cancellation:
        return "Operation was cancelled by user"

    if error_info.is_auth:
        return "Authentication failed. Please check your API key."

    if error_info.is_quota_exhausted:
        return (
            "Usage limit reached. Agent has been paused. "
            "Please wait for your quota to reset or upgrade your plan."
        )

    if error_info.is_rate_limit:
        retry_msg = (
            f" Please wait {error_info.retry_after} seconds before retrying."
            if error_info.retry_after
            else " Please reduce concurrency or wait before retrying."
        )
        return f"Rate limit exceeded (429).{retry_msg}"

    if error_info.type == ErrorType.CONTEXT_LENGTH:
        return (
            "Context length exceeded. The conversation or file content is too large. "
            "Try reducing the context or splitting the task."
        )

    if error_info.type == ErrorType.NETWORK:
        return (
            "Network error occurred. Please check your internet connection and try again."
        )

    if error_info.type == ErrorType.BROWSER:
        return (
            "Browser automation error. Playwright browser may not be installed. "
            "Try running 'npx playwright install chromium' or use YOLO mode."
        )

    # Return original message for other errors
    return error_info.message


def get_error_message(error: Any) -> str:
    """
    Extract error message from an unknown error value.

    Simple utility for getting a string error message from any error type.

    Args:
        error: The error value (Exception, string, or unknown)

    Returns:
        Error message string
    """
    if isinstance(error, Exception):
        return str(error)
    return str(error) if error else "Unknown error"
