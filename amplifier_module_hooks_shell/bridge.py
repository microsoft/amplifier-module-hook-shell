"""
Main bridge module for shell hooks.

Coordinates loading, matching, execution, and translation of hooks.
"""

import logging
from pathlib import Path
from typing import Any

from amplifier_module_hooks_shell.executor import HookExecutor
from amplifier_module_hooks_shell.loader import HookConfigLoader
from amplifier_module_hooks_shell.matcher import MatcherGroup
from amplifier_module_hooks_shell.translator import DataTranslator

logger = logging.getLogger(__name__)


class ShellHookBridge:
    """Bridge that executes shell hooks in Amplifier."""

    # Map Claude Code events to our internal event names
    CLAUDE_EVENT_MAP = {
        "tool:pre": "PreToolUse",
        "tool:post": "PostToolUse",
        "prompt:submit": "UserPromptSubmit",
        "session:start": "SessionStart",
        "session:end": "SessionEnd",
    }

    def __init__(self, config: dict[str, Any]):
        """
        Initialize bridge.

        Args:
            config: Module configuration from bundle YAML
        """
        self.config = config
        self.enabled = config.get("enabled", True)

        # Discover hooks directory
        project_dir = Path.cwd()
        hooks_dir = project_dir / ".amplifier" / "hooks"

        if not hooks_dir.exists():
            logger.info(f"Hooks directory not found at {hooks_dir}")
            self.hook_configs = {"hooks": {}}
        else:
            # Load configurations
            loader = HookConfigLoader(hooks_dir)
            self.hook_configs = loader.load_all_configs()
            hook_events = list(self.hook_configs.get("hooks", {}).keys())
            logger.info(f"Loaded hook configs from {hooks_dir}: {hook_events}")

        # Initialize components
        self.project_dir = project_dir
        self.hooks_dir = hooks_dir
        self.translator = DataTranslator()
        self.executor: HookExecutor | None = None

        # Create matcher groups for each event
        self.matcher_groups: dict[str, MatcherGroup] = {}
        for event_name, matchers_config in self.hook_configs.get("hooks", {}).items():
            self.matcher_groups[event_name] = MatcherGroup(matchers_config)
            logger.debug(f"Created matcher group for {event_name}")

    def _get_executor(self, session_id: str = "unknown") -> HookExecutor:
        """Get or create executor."""
        if self.executor is None:
            self.executor = HookExecutor(self.project_dir, self.hooks_dir, session_id)
        return self.executor

    async def _execute_hooks(self, amplifier_event: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute matching hooks for an event.

        Args:
            amplifier_event: Amplifier event name (e.g., "tool:pre")
            data: Event data from Amplifier

        Returns:
            HookResult fields dict
        """

        if not self.enabled:
            return {"action": "continue"}

        # Map to Claude Code event name
        claude_event = self.CLAUDE_EVENT_MAP.get(amplifier_event)
        if not claude_event or claude_event not in self.matcher_groups:
            return {"action": "continue"}

        matcher_group = self.matcher_groups[claude_event]

        # Extract tool name for matching
        tool_name = data.get("tool_name", data.get("name", ""))

        # Get matching hooks
        matching_hooks = matcher_group.get_matching_hooks(tool_name)

        if not matching_hooks:
            logger.debug(f"No matching hooks for {claude_event} with tool {tool_name}")
            return {"action": "continue"}

        logger.info(f"Found {len(matching_hooks)} matching hooks for {claude_event}")

        # Translate data to Claude Code format
        claude_data = self.translator.to_claude_format(claude_event, data)

        # Get executor
        session_id = data.get("session_id", "unknown")
        executor = self._get_executor(session_id)

        # Execute all matching hooks
        for hook_config in matching_hooks:
            if hook_config.get("type") != "command":
                continue

            command = hook_config["command"]
            timeout = hook_config.get("timeout", 30.0)

            logger.info(f"Executing hook: {command}")

            # Execute hook
            exit_code, stdout, stderr = await executor.execute(command, claude_data, timeout)

            logger.debug(
                f"Hook result: exit_code={exit_code}, stdout={stdout[:100] if stdout else ''}"
            )

            # Translate response
            result_fields = self.translator.from_claude_response(exit_code, stdout, stderr)

            # If this hook blocks or modifies, return immediately
            action = result_fields.get("action", "continue")
            if action in ("deny", "modify", "inject_context"):
                logger.info(f"Hook returned action: {action}")
                return result_fields

        return {"action": "continue"}

    async def on_tool_pre(self, event: str, data: dict[str, Any]):
        """Handle tool:pre events."""
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("tool:pre", data)
        return HookResult(**result)

    async def on_tool_post(self, event: str, data: dict[str, Any]):
        """Handle tool:post events."""
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("tool:post", data)
        return HookResult(**result)

    async def on_prompt_submit(self, event: str, data: dict[str, Any]):
        """Handle prompt:submit events."""
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("prompt:submit", data)
        return HookResult(**result)

    async def on_session_start(self, event: str, data: dict[str, Any]):
        """Handle session:start events."""
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("session:start", data)
        return HookResult(**result)

    async def on_session_end(self, event: str, data: dict[str, Any]):
        """Handle session:end events."""
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("session:end", data)
        return HookResult(**result)
