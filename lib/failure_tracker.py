"""
Failure Tracker
===============

Tracks consecutive failures and triggers auto-pause when threshold is reached.
Prevents cascading failures and saves API credits by detecting quota/rate limit issues.

Ported from automaker/apps/server/src/services/auto-mode-service.ts
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable, List

from .error_classifier import ErrorInfo, ErrorType

logger = logging.getLogger(__name__)


# Configuration constants
FAILURE_WINDOW_SECONDS = 60  # 1 minute window for tracking failures
CONSECUTIVE_FAILURE_THRESHOLD = 3  # Pause after 3 failures in the window


@dataclass
class FailureRecord:
    """Record of a single failure."""
    timestamp: datetime
    error_info: ErrorInfo
    feature_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "error_type": self.error_info.type.value,
            "error_message": self.error_info.message,
            "feature_id": self.feature_id,
        }


@dataclass
class FailureStats:
    """Statistics about failures."""
    total_failures: int = 0
    failures_in_window: int = 0
    last_failure_time: Optional[datetime] = None
    paused_due_to_failures: bool = False
    pause_reason: Optional[str] = None


class FailureTracker:
    """
    Tracks consecutive failures and determines when to pause.

    Features:
    - Time-windowed failure tracking (1 minute window)
    - Automatic pause after threshold reached
    - Immediate pause for quota/rate limit errors
    - Callbacks for pause events
    - Success tracking to reset failure count

    Usage:
        tracker = FailureTracker(on_pause_triggered=my_callback)

        try:
            # ... agent work ...
        except Exception as e:
            error_info = classify_error(e)
            if tracker.track_failure(error_info, feature_id=42):
                # Should pause - too many failures
                break
    """

    def __init__(
        self,
        failure_window_seconds: int = FAILURE_WINDOW_SECONDS,
        consecutive_threshold: int = CONSECUTIVE_FAILURE_THRESHOLD,
        on_pause_triggered: Optional[Callable[[FailureStats, ErrorInfo], None]] = None,
    ):
        """
        Initialize the failure tracker.

        Args:
            failure_window_seconds: Time window for tracking consecutive failures
            consecutive_threshold: Number of failures in window before triggering pause
            on_pause_triggered: Callback function called when pause is triggered
        """
        self.failure_window_seconds = failure_window_seconds
        self.consecutive_threshold = consecutive_threshold
        self.on_pause_triggered = on_pause_triggered

        self._failures: List[FailureRecord] = []
        self._paused_due_to_failures = False
        self._total_failures = 0
        self._pause_reason: Optional[str] = None

    @property
    def is_paused(self) -> bool:
        """Check if tracker is in paused state."""
        return self._paused_due_to_failures

    @property
    def failures_in_window(self) -> int:
        """Get count of failures in current time window."""
        self._cleanup_old_failures()
        return len(self._failures)

    def track_failure(
        self,
        error_info: ErrorInfo,
        feature_id: Optional[int] = None,
    ) -> bool:
        """
        Track a failure and check if we should pause.

        Args:
            error_info: Classified error information
            feature_id: ID of the feature that failed (optional)

        Returns:
            True if we should pause (too many failures or critical error)
        """
        now = datetime.now(timezone.utc)
        self._total_failures += 1

        # Create failure record
        record = FailureRecord(
            timestamp=now,
            error_info=error_info,
            feature_id=feature_id,
        )
        self._failures.append(record)

        # Clean up old failures outside the window
        self._cleanup_old_failures()

        logger.debug(
            f"Tracked failure: {error_info.type.value} "
            f"(failures in window: {len(self._failures)}/{self.consecutive_threshold})"
        )

        # Check if we should pause
        should_pause = self._should_pause(error_info)

        if should_pause:
            self._trigger_pause(error_info)

        return should_pause

    def _cleanup_old_failures(self) -> None:
        """Remove failures outside the time window."""
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - self.failure_window_seconds

        self._failures = [
            f for f in self._failures
            if f.timestamp.timestamp() >= cutoff
        ]

    def _should_pause(self, error_info: ErrorInfo) -> bool:
        """
        Check if we should pause based on current failures.

        Args:
            error_info: The latest error info

        Returns:
            True if we should pause
        """
        # Already paused
        if self._paused_due_to_failures:
            return False

        # Check if we've hit the threshold
        if len(self._failures) >= self.consecutive_threshold:
            return True

        # Immediately pause for known quota/rate limit errors
        if error_info.type in (ErrorType.QUOTA_EXHAUSTED, ErrorType.RATE_LIMIT):
            return True

        # Immediately pause for authentication errors
        if error_info.type == ErrorType.AUTHENTICATION:
            return True

        return False

    def _trigger_pause(self, error_info: ErrorInfo) -> None:
        """
        Trigger pause and notify via callback.

        Args:
            error_info: The error that triggered the pause
        """
        self._paused_due_to_failures = True
        failure_count = len(self._failures)

        # Determine pause reason
        if error_info.type == ErrorType.QUOTA_EXHAUSTED:
            self._pause_reason = f"Quota exhausted: {error_info.message}"
        elif error_info.type == ErrorType.RATE_LIMIT:
            retry_msg = (
                f" (retry after {error_info.retry_after}s)"
                if error_info.retry_after
                else ""
            )
            self._pause_reason = f"Rate limit exceeded{retry_msg}"
        elif error_info.type == ErrorType.AUTHENTICATION:
            self._pause_reason = "Authentication failed"
        else:
            self._pause_reason = (
                f"Too many consecutive failures ({failure_count} in "
                f"{self.failure_window_seconds}s): {error_info.type.value}"
            )

        logger.warning(
            f"Auto-pause triggered: {self._pause_reason}"
        )

        # Call callback if provided
        if self.on_pause_triggered:
            stats = self.get_stats()
            try:
                self.on_pause_triggered(stats, error_info)
            except Exception as e:
                logger.error(f"Error in pause callback: {e}")

    def record_success(self) -> None:
        """
        Record a successful operation to reset consecutive failure count.

        Call this after each successful feature completion.
        """
        self._failures = []
        logger.debug("Failure tracker: recorded success, reset failures")

    def reset(self) -> None:
        """
        Reset tracker to initial state.

        Call this when user manually restarts the agent.
        """
        self._failures = []
        self._paused_due_to_failures = False
        self._pause_reason = None
        logger.info("Failure tracker reset")

    def resume(self) -> None:
        """
        Resume from paused state.

        Call this when user manually resumes after a pause.
        """
        self._paused_due_to_failures = False
        self._pause_reason = None
        self._failures = []  # Clear failures to give fresh start
        logger.info("Failure tracker resumed")

    def get_stats(self) -> FailureStats:
        """
        Get current failure statistics.

        Returns:
            FailureStats with current state
        """
        self._cleanup_old_failures()

        last_failure_time = None
        if self._failures:
            last_failure_time = self._failures[-1].timestamp

        return FailureStats(
            total_failures=self._total_failures,
            failures_in_window=len(self._failures),
            last_failure_time=last_failure_time,
            paused_due_to_failures=self._paused_due_to_failures,
            pause_reason=self._pause_reason,
        )

    def get_recent_failures(self, count: int = 10) -> List[FailureRecord]:
        """
        Get most recent failure records.

        Args:
            count: Maximum number of records to return

        Returns:
            List of recent failure records
        """
        return self._failures[-count:] if self._failures else []
