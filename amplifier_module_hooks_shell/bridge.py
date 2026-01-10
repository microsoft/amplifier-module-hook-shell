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

    # Map Amplifier events to Claude Code event names
    # Phase 1 events
    CLAUDE_EVENT_MAP = {
        "tool:pre": "PreToolUse",
        "tool:post": "PostToolUse",
        "prompt:submit": "UserPromptSubmit",
        "session:start": "SessionStart",
        "session:end": "SessionEnd",
        # Phase 2 events
        "prompt:complete": "Stop",
        "context:pre_compact": "PreCompact",
        "approval:required": "PermissionRequest",
        "session:resume": "SessionStart",  # Maps to SessionStart with trigger=resume
        "user:notification": "Notification",
    }

    # Events that support blocking/modification
    BLOCKING_EVENTS = {
        "PreToolUse",
        "UserPromptSubmit",
        "Stop",
        "PermissionRequest",
    }

    # Events that support context injection
    CONTEXT_INJECTION_EVENTS = {
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "SessionStart",
        "PreCompact",
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

        # Create matcher groups for each event (from directory-based hooks)
        self.matcher_groups: dict[str, MatcherGroup] = {}
        for event_name, matchers_config in self.hook_configs.get("hooks", {}).items():
            self.matcher_groups[event_name] = MatcherGroup(matchers_config)
            logger.debug(f"Created matcher group for {event_name}")

        # Track skill-scoped hooks (skill_name -> hooks config)
        self.skill_scoped_hooks: dict[str, dict[str, Any]] = {}
        # Track skill-scoped matcher groups (skill_name -> {event -> MatcherGroup})
        self.skill_matcher_groups: dict[str, dict[str, MatcherGroup]] = {}

    def _get_executor(self, session_id: str = "unknown") -> HookExecutor:
        """Get or create executor."""
        if self.executor is None:
            self.executor = HookExecutor(self.project_dir, self.hooks_dir, session_id)
        return self.executor

    async def _execute_hooks(self, amplifier_event: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute matching hooks for an event.

        Checks both directory-based hooks and skill-scoped hooks.

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
        if not claude_event:
            return {"action": "continue"}

        # Extract matcher target based on event type
        # SessionStart uses "trigger" for matching (startup, resume, clear, compact)
        # Tool events use "tool_name" for matching
        if claude_event == "SessionStart":
            match_target = data.get("trigger", "startup")
        else:
            match_target = data.get("tool_name", data.get("name", ""))

        # Collect matching hooks from all sources
        matching_hooks: list[dict[str, Any]] = []

        # 1. Directory-based hooks (.amplifier/hooks/)
        if claude_event in self.matcher_groups:
            dir_hooks = self.matcher_groups[claude_event].get_matching_hooks(match_target)
            matching_hooks.extend(dir_hooks)

        # 2. Skill-scoped hooks (from loaded skills)
        for skill_name, skill_matchers in self.skill_matcher_groups.items():
            if claude_event in skill_matchers:
                skill_hooks = skill_matchers[claude_event].get_matching_hooks(match_target)
                if skill_hooks:
                    logger.debug(f"Found {len(skill_hooks)} hooks from skill '{skill_name}'")
                    matching_hooks.extend(skill_hooks)

        if not matching_hooks:
            logger.debug(f"No matching hooks for {claude_event} with target {match_target}")
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

    # --- Phase 2 Event Handlers ---

    async def on_prompt_complete(self, event: str, data: dict[str, Any]):
        """
        Handle prompt:complete events (Stop hook).

        This fires when the orchestrator completes a prompt. Hooks can prevent
        the stop (return action=deny to continue the conversation).
        """
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("prompt:complete", data)
        return HookResult(**result)

    async def on_context_pre_compact(self, event: str, data: dict[str, Any]):
        """
        Handle context:pre_compact events (PreCompact hook).

        This fires before context compaction. Hooks can inject context
        or perform cleanup before compaction occurs.
        """
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("context:pre_compact", data)
        return HookResult(**result)

    async def on_approval_required(self, event: str, data: dict[str, Any]):
        """
        Handle approval:required events (PermissionRequest hook).

        This fires when an operation requires user approval. Hooks can
        auto-approve (action=continue) or auto-deny (action=deny).
        """
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("approval:required", data)
        return HookResult(**result)

    async def on_session_resume(self, event: str, data: dict[str, Any]):
        """
        Handle session:resume events.

        Maps to SessionStart with trigger=resume for hooks that need to
        differentiate between fresh starts and resumes.
        """
        from amplifier_core.models import HookResult

        # Add trigger info for hooks that care about resume vs start
        data_with_trigger = {**data, "trigger": "resume"}
        result = await self._execute_hooks("session:resume", data_with_trigger)
        return HookResult(**result)

    async def on_user_notification(self, event: str, data: dict[str, Any]):
        """
        Handle user:notification events (Notification hook).

        This fires when a notification is shown to the user. Hooks can
        intercept or augment notifications.
        """
        from amplifier_core.models import HookResult

        result = await self._execute_hooks("user:notification", data)
        return HookResult(**result)

    # --- Skill-Scoped Hook Management ---

    async def on_skill_loaded(self, event: str, data: dict[str, Any]):
        """
        Handle skill:loaded events - register skill-scoped hooks.

        When a skill with embedded hooks is loaded, we register those hooks
        so they become active for the rest of the session.

        Args:
            event: Event name ("skill:loaded")
            data: Event data containing skill_name, hooks config, etc.
        """
        from amplifier_core.models import HookResult

        skill_name = data.get("skill_name")
        hooks_config = data.get("hooks")

        if not skill_name or not hooks_config:
            return HookResult(action="continue")

        # Store the hooks config for this skill
        self.skill_scoped_hooks[skill_name] = hooks_config

        # Create matcher groups for each event in the skill's hooks
        skill_matchers: dict[str, MatcherGroup] = {}
        for event_name, matchers_config in hooks_config.items():
            skill_matchers[event_name] = MatcherGroup(matchers_config)
            logger.debug(f"Created skill-scoped matcher group for {skill_name}:{event_name}")

        self.skill_matcher_groups[skill_name] = skill_matchers

        # Resolve relative paths in hook commands to be relative to skill directory
        skill_dir = data.get("skill_directory")
        if skill_dir:
            self._resolve_skill_hook_paths(skill_name, skill_dir)

        logger.info(f"Registered {len(hooks_config)} hook events for skill '{skill_name}'")

        return HookResult(action="continue")

    async def on_skill_unloaded(self, event: str, data: dict[str, Any]):
        """
        Handle skill:unloaded events - cleanup skill-scoped hooks.

        When a skill is unloaded (e.g., session end), we remove its hooks.

        Args:
            event: Event name ("skill:unloaded")
            data: Event data containing skill_name
        """
        from amplifier_core.models import HookResult

        skill_name = data.get("skill_name")
        if not skill_name:
            return HookResult(action="continue")

        # Remove skill's hooks
        if skill_name in self.skill_scoped_hooks:
            del self.skill_scoped_hooks[skill_name]
            logger.debug(f"Removed hooks config for skill '{skill_name}'")

        if skill_name in self.skill_matcher_groups:
            del self.skill_matcher_groups[skill_name]
            logger.debug(f"Removed matcher groups for skill '{skill_name}'")

        logger.info(f"Unregistered hooks for skill '{skill_name}'")

        return HookResult(action="continue")

    def _resolve_skill_hook_paths(self, skill_name: str, skill_dir: str) -> None:
        """
        Resolve relative paths in skill hook commands.

        Commands like "./scripts/check.sh" become absolute paths relative
        to the skill's directory.

        Args:
            skill_name: Name of the skill
            skill_dir: Absolute path to the skill's directory
        """
        hooks_config = self.skill_scoped_hooks.get(skill_name, {})
        skill_path = Path(skill_dir)

        for event_name, matchers in hooks_config.items():
            if not isinstance(matchers, list):
                continue
            for matcher_config in matchers:
                hooks = matcher_config.get("hooks", [])
                if not isinstance(hooks, list):
                    continue
                for hook in hooks:
                    if hook.get("type") == "command":
                        command = hook.get("command", "")
                        # Resolve relative paths (starting with ./ or ../)
                        if command.startswith("./") or command.startswith("../"):
                            resolved = skill_path / command
                            hook["command"] = str(resolved.resolve())
                            logger.debug(f"Resolved hook path: {command} -> {hook['command']}")
