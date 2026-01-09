"""
Loop Detector
=============

Detects repetitive patterns in agent actions to prevent infinite loops.

Detection strategies:
1. Exact repetition: Same action repeated N times
2. Pattern repetition: Same sequence of actions repeated
3. Semantic similarity: Similar actions (edit same file, same error)
4. Output similarity: Similar tool outputs indicating stuck state
"""

import hashlib
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class Action:
    """Represents an agent action."""
    action_type: str  # e.g., "tool_call", "edit", "bash", "read"
    content: str  # Action content/description
    target: Optional[str] = None  # Target file/resource
    output: Optional[str] = None  # Tool output
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Generate a fingerprint for this action."""
        data = f"{self.action_type}:{self.target or ''}:{self.content[:200]}"
        return hashlib.md5(data.encode()).hexdigest()[:16]

    @property
    def short_fingerprint(self) -> str:
        """Generate a short fingerprint (type + target only)."""
        return f"{self.action_type}:{self.target or 'none'}"


class LoopPattern:
    """Detected loop pattern."""
    def __init__(
        self,
        pattern_type: str,
        repetitions: int,
        actions: list[Action],
        confidence: float,
        description: str,
    ):
        self.pattern_type = pattern_type
        self.repetitions = repetitions
        self.actions = actions
        self.confidence = confidence
        self.description = description
        self.detected_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type,
            "repetitions": self.repetitions,
            "confidence": self.confidence,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "action_count": len(self.actions),
        }


class LoopDetector:
    """
    Detects repetitive patterns in agent actions.

    Configuration:
    - max_history: Maximum actions to keep in history
    - exact_threshold: Number of identical actions to trigger
    - pattern_threshold: Number of pattern repetitions to trigger
    - similarity_threshold: Similarity score (0-1) for similar actions
    """

    def __init__(
        self,
        max_history: int = 100,
        exact_threshold: int = 5,
        pattern_threshold: int = 3,
        similarity_threshold: float = 0.85,
        on_loop_detected: Optional[Callable[[LoopPattern], None]] = None,
    ):
        """
        Initialize the loop detector.

        Args:
            max_history: Maximum actions to track
            exact_threshold: Identical actions before detection
            pattern_threshold: Pattern repetitions before detection
            similarity_threshold: Similarity score threshold
            on_loop_detected: Callback when loop is detected
        """
        self.max_history = max_history
        self.exact_threshold = exact_threshold
        self.pattern_threshold = pattern_threshold
        self.similarity_threshold = similarity_threshold
        self.on_loop_detected = on_loop_detected

        self.actions: deque[Action] = deque(maxlen=max_history)
        self.detected_patterns: list[LoopPattern] = []
        self._suppressed_until: Optional[datetime] = None

    def record_action(self, action: Action) -> Optional[LoopPattern]:
        """
        Record an action and check for loops.

        Args:
            action: The action to record

        Returns:
            LoopPattern if a loop is detected, None otherwise
        """
        self.actions.append(action)

        # Skip detection if suppressed
        if self._suppressed_until and datetime.now(timezone.utc) < self._suppressed_until:
            return None

        # Run detection strategies
        pattern = self._detect_loops()

        if pattern:
            self.detected_patterns.append(pattern)
            logger.warning(f"Loop detected: {pattern.description}")

            if self.on_loop_detected:
                try:
                    self.on_loop_detected(pattern)
                except Exception as e:
                    logger.error(f"Loop callback error: {e}")

        return pattern

    def _detect_loops(self) -> Optional[LoopPattern]:
        """Run all loop detection strategies."""
        # Strategy 1: Exact repetition
        pattern = self._detect_exact_repetition()
        if pattern:
            return pattern

        # Strategy 2: Pattern repetition (sequences)
        pattern = self._detect_pattern_repetition()
        if pattern:
            return pattern

        # Strategy 3: Semantic similarity
        pattern = self._detect_similar_actions()
        if pattern:
            return pattern

        # Strategy 4: Error loop (same error repeated)
        pattern = self._detect_error_loop()
        if pattern:
            return pattern

        return None

    def _detect_exact_repetition(self) -> Optional[LoopPattern]:
        """Detect exact same action repeated."""
        if len(self.actions) < self.exact_threshold:
            return None

        recent = list(self.actions)[-self.exact_threshold:]
        fingerprints = [a.fingerprint for a in recent]

        if len(set(fingerprints)) == 1:
            return LoopPattern(
                pattern_type="exact_repetition",
                repetitions=self.exact_threshold,
                actions=recent,
                confidence=1.0,
                description=f"Same action repeated {self.exact_threshold} times: {recent[0].action_type} on {recent[0].target or 'unknown'}",
            )

        return None

    def _detect_pattern_repetition(self) -> Optional[LoopPattern]:
        """Detect repeating sequence of actions."""
        if len(self.actions) < self.pattern_threshold * 2:
            return None

        actions_list = list(self.actions)

        # Try different pattern lengths (2-10 actions)
        for pattern_len in range(2, min(11, len(actions_list) // self.pattern_threshold)):
            pattern = [a.fingerprint for a in actions_list[-pattern_len:]]

            # Count how many times this pattern appears
            repetitions = 0
            for i in range(len(actions_list) - pattern_len, -1, -pattern_len):
                if i < 0:
                    break
                segment = [a.fingerprint for a in actions_list[i:i + pattern_len]]
                if segment == pattern:
                    repetitions += 1
                else:
                    break

            if repetitions >= self.pattern_threshold:
                return LoopPattern(
                    pattern_type="pattern_repetition",
                    repetitions=repetitions,
                    actions=actions_list[-pattern_len * repetitions:],
                    confidence=0.9,
                    description=f"Sequence of {pattern_len} actions repeated {repetitions} times",
                )

        return None

    def _detect_similar_actions(self) -> Optional[LoopPattern]:
        """Detect semantically similar actions."""
        if len(self.actions) < self.exact_threshold:
            return None

        recent = list(self.actions)[-self.exact_threshold:]

        # Group by target
        targets = {}
        for action in recent:
            target = action.target or "none"
            if target not in targets:
                targets[target] = []
            targets[target].append(action)

        # Check for similar content on same target
        for target, target_actions in targets.items():
            if len(target_actions) < self.exact_threshold - 1:
                continue

            # Compare content similarity
            similar_count = 0
            for i in range(len(target_actions) - 1):
                for j in range(i + 1, len(target_actions)):
                    similarity = SequenceMatcher(
                        None,
                        target_actions[i].content[:500],
                        target_actions[j].content[:500]
                    ).ratio()
                    if similarity >= self.similarity_threshold:
                        similar_count += 1

            # If most pairs are similar, we have a loop
            total_pairs = len(target_actions) * (len(target_actions) - 1) // 2
            if total_pairs > 0 and similar_count / total_pairs > 0.7:
                return LoopPattern(
                    pattern_type="similar_actions",
                    repetitions=len(target_actions),
                    actions=target_actions,
                    confidence=0.8,
                    description=f"Similar actions on {target}: {len(target_actions)} times",
                )

        return None

    def _detect_error_loop(self) -> Optional[LoopPattern]:
        """Detect repeated errors."""
        if len(self.actions) < 3:
            return None

        recent = list(self.actions)[-10:]

        # Look for error patterns in output
        error_patterns = []
        for action in recent:
            if action.output and self._contains_error(action.output):
                error_hash = self._extract_error_hash(action.output)
                error_patterns.append(error_hash)

        if len(error_patterns) >= 3:
            # Check if same error appears multiple times
            from collections import Counter
            counts = Counter(error_patterns)
            most_common, count = counts.most_common(1)[0]

            if count >= 3:
                error_actions = [
                    a for a in recent
                    if a.output and self._extract_error_hash(a.output) == most_common
                ]
                return LoopPattern(
                    pattern_type="error_loop",
                    repetitions=count,
                    actions=error_actions,
                    confidence=0.85,
                    description=f"Same error repeated {count} times",
                )

        return None

    def _contains_error(self, text: str) -> bool:
        """Check if text contains an error indication."""
        error_indicators = [
            r"error:",
            r"Error:",
            r"ERROR",
            r"failed",
            r"Failed",
            r"exception",
            r"Exception",
            r"traceback",
            r"Traceback",
        ]
        return any(re.search(pattern, text) for pattern in error_indicators)

    def _extract_error_hash(self, text: str) -> str:
        """Extract a hash of the error message."""
        # Find error line
        lines = text.split("\n")
        error_lines = [
            line for line in lines
            if any(ind in line.lower() for ind in ["error", "failed", "exception"])
        ]

        if error_lines:
            # Hash first error line
            return hashlib.md5(error_lines[0].encode()).hexdigest()[:8]

        # Fall back to full text hash
        return hashlib.md5(text[:200].encode()).hexdigest()[:8]

    def suppress(self, seconds: int = 60) -> None:
        """
        Temporarily suppress loop detection.

        Useful after taking corrective action.

        Args:
            seconds: Seconds to suppress detection
        """
        from datetime import timedelta
        self._suppressed_until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        logger.info(f"Loop detection suppressed for {seconds} seconds")

    def clear_history(self) -> None:
        """Clear action history."""
        self.actions.clear()
        logger.info("Loop detector history cleared")

    def get_stats(self) -> dict:
        """Get loop detector statistics."""
        return {
            "action_count": len(self.actions),
            "max_history": self.max_history,
            "patterns_detected": len(self.detected_patterns),
            "is_suppressed": bool(
                self._suppressed_until and
                datetime.now(timezone.utc) < self._suppressed_until
            ),
            "recent_actions": [
                {
                    "type": a.action_type,
                    "target": a.target,
                    "fingerprint": a.fingerprint,
                }
                for a in list(self.actions)[-5:]
            ],
        }

    def get_recent_patterns(self, count: int = 5) -> list[dict]:
        """Get recently detected patterns."""
        return [p.to_dict() for p in self.detected_patterns[-count:]]


def create_action_from_tool_call(
    tool_name: str,
    tool_input: dict,
    tool_output: Optional[str] = None,
) -> Action:
    """
    Create an Action from a tool call.

    Args:
        tool_name: Name of the tool called
        tool_input: Tool input parameters
        tool_output: Tool output (if available)

    Returns:
        Action object
    """
    # Determine target based on tool type
    target = None
    if "file_path" in tool_input:
        target = tool_input["file_path"]
    elif "path" in tool_input:
        target = tool_input["path"]
    elif "command" in tool_input:
        target = tool_input["command"][:50]

    # Create content summary
    content = str(tool_input)[:500]

    return Action(
        action_type=tool_name,
        content=content,
        target=target,
        output=tool_output[:1000] if tool_output else None,
    )
