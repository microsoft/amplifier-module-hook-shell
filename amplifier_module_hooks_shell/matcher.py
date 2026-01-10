"""
Matcher for filtering hooks by tool name.

Implements Claude Code's regex-based matcher system.
"""

import re
from typing import Any


class HookMatcher:
    """Match tool names against Claude Code patterns."""

    def __init__(self, pattern: str):
        """
        Initialize matcher.

        Args:
            pattern: Regex pattern or exact match string
        """
        self.pattern = pattern
        self._compiled_regex = self._compile_pattern(pattern)

    def _compile_pattern(self, pattern: str) -> re.Pattern[str] | None:
        """
        Compile matcher pattern to regex.

        Args:
            pattern: Pattern string

        Returns:
            Compiled regex or None for match-all patterns
        """
        # Match all patterns
        if not pattern or pattern == "*":
            return None

        try:
            # Try to compile as regex (case-insensitive for tool name matching)
            return re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Invalid regex - will do exact match fallback
            return None

    def matches(self, tool_name: str) -> bool:
        """
        Check if tool name matches the pattern.

        Args:
            tool_name: Name of the tool to match

        Returns:
            True if matches, False otherwise
        """
        # Match-all pattern
        if self._compiled_regex is None and (not self.pattern or self.pattern == "*"):
            return True

        # Regex match
        if self._compiled_regex:
            return bool(self._compiled_regex.fullmatch(tool_name))

        # Fallback: case-insensitive exact match
        return tool_name.lower() == self.pattern.lower()


class MatcherGroup:
    """Group of matchers for a specific event."""

    def __init__(self, matchers_config: list[dict[str, Any]]):
        """
        Initialize matcher group.

        Args:
            matchers_config: List of matcher configurations
        """
        self.matchers: list[tuple[HookMatcher, list[dict[str, Any]]]] = []

        for matcher_config in matchers_config:
            pattern = matcher_config.get("matcher", "*")
            hooks = matcher_config.get("hooks", [])

            if hooks:  # Only add if there are hooks
                matcher = HookMatcher(pattern)
                self.matchers.append((matcher, hooks))

    def get_matching_hooks(self, tool_name: str) -> list[dict[str, Any]]:
        """
        Get all hooks that match the given tool name.

        Args:
            tool_name: Name of the tool

        Returns:
            List of hook configurations that match
        """
        matching = []

        for matcher, hooks in self.matchers:
            if matcher.matches(tool_name):
                matching.extend(hooks)

        return matching
