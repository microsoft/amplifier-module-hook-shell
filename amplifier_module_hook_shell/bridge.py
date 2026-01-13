"""
Main bridge module for shell hooks.

Coordinates loading, matching, execution, and translation of hooks.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from amplifier_module_hook_shell.executor import HookExecutor
from amplifier_module_hook_shell.loader import HookConfigLoader
from amplifier_module_hook_shell.matcher import MatcherGroup
from amplifier_module_hook_shell.translator import DataTranslator

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

    def __init__(self, config: dict[str, Any], coordinator: Any = None):
        """
        Initialize bridge.

        Args:
            config: Module configuration from bundle YAML
            coordinator: Module coordinator for provider access (optional for tests)
        """
        self.config = config
        self.coordinator = coordinator
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

    def _expand_arguments(self, prompt: str, data: dict[str, Any]) -> str:
        """
        Expand $ARGUMENTS placeholder in prompt with event context.

        Args:
            prompt: The prompt template with possible $ARGUMENTS placeholder
            data: Event data to extract arguments from

        Returns:
            Expanded prompt string
        """
        import json

        if "$ARGUMENTS" not in prompt:
            return prompt

        # Build arguments string from event data
        # Include key context fields that are useful for evaluation
        arguments_parts = []

        if "prompt" in data:
            arguments_parts.append(f"User prompt: {data['prompt']}")
        if "name" in data or "tool_name" in data:
            tool_name = data.get("name", data.get("tool_name", ""))
            arguments_parts.append(f"Tool: {tool_name}")
        if "input" in data:
            arguments_parts.append(f"Input: {json.dumps(data['input'], indent=2)}")
        if "result" in data:
            result_str = json.dumps(data["result"], indent=2)
            # Truncate long results
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            arguments_parts.append(f"Result: {result_str}")
        if "trigger" in data:
            arguments_parts.append(f"Trigger: {data['trigger']}")

        arguments = "\n".join(arguments_parts) if arguments_parts else json.dumps(data)
        return prompt.replace("$ARGUMENTS", arguments)

    async def _execute_prompt_hook(self, prompt: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a prompt-based hook using the registered LLM provider.

        Args:
            prompt: The prompt template (may contain $ARGUMENTS)
            data: Event context data for placeholder expansion

        Returns:
            Dict with 'ok' (bool) and 'reason' (str) fields
        """

        # Expand $ARGUMENTS placeholder
        expanded_prompt = self._expand_arguments(prompt, data)

        # Get provider from coordinator
        if not self.coordinator:
            logger.warning("No coordinator available for prompt hook, defaulting to ok=True")
            return {"ok": True, "reason": "No provider available"}

        try:
            providers = self.coordinator.get("providers")
        except Exception as e:
            logger.warning(f"Failed to get providers: {e}, defaulting to ok=True")
            return {"ok": True, "reason": "Provider access failed"}

        if not providers:
            logger.warning("No providers registered for prompt hook, defaulting to ok=True")
            return {"ok": True, "reason": "No provider available"}

        # Get first available provider
        provider = next(iter(providers.values()))

        try:
            # Import message models for ChatRequest
            from amplifier_core.message_models import ChatRequest, Message, TextBlock

            # Create request with the expanded prompt
            request = ChatRequest(
                messages=[
                    Message(
                        role="user",
                        content=[TextBlock(type="text", text=expanded_prompt)],
                    )
                ],
                max_output_tokens=256,  # Keep responses short
            )

            # Call provider
            response = await provider.complete(request)

            # Extract text from response
            if response.content and len(response.content) > 0:
                response_text = response.content[0].text
            else:
                logger.warning("Empty response from provider, defaulting to ok=True")
                return {"ok": True, "reason": "Empty provider response"}

            # Parse response for {ok: true/false, reason: "..."}
            return self._parse_prompt_response(response_text)

        except Exception as e:
            logger.warning(f"Prompt hook execution failed: {e}, defaulting to ok=True")
            return {"ok": True, "reason": f"Execution error: {e}"}

    def _parse_prompt_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse LLM response for ok/reason decision.

        Handles:
        - JSON: {"ok": true/false, "reason": "..."}
        - Simple: "yes"/"no", "true"/"false"
        - Defaults to ok=True on parse failure (fail open)

        Args:
            response_text: Raw text response from LLM

        Returns:
            Dict with 'ok' (bool) and 'reason' (str) fields
        """
        import json
        import re

        response_text = response_text.strip()

        # Try to extract JSON from response (may be wrapped in markdown code blocks)
        json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                ok_value = parsed.get("ok", True)

                # Handle various truthy/falsy representations
                if isinstance(ok_value, bool):
                    ok = ok_value
                elif isinstance(ok_value, str):
                    ok = ok_value.lower() in ("true", "yes", "1", "ok")
                else:
                    ok = bool(ok_value)

                reason = parsed.get("reason", "")
                return {"ok": ok, "reason": reason}
            except json.JSONDecodeError:
                pass

        # Try simple yes/no detection (check for explicit indicators)
        lower_text = response_text.lower()
        # Check for negative indicators - be specific to avoid false matches
        negative_patterns = [
            "not complete",
            "incomplete",
            "not done",
            "not yet",
            "more work",
            "needs more",
        ]
        positive_patterns = ["yes", "complete", "done", "finished", "fully addressed"]

        # Check negative patterns first (they're more specific)
        if any(pattern in lower_text for pattern in negative_patterns):
            return {"ok": False, "reason": response_text[:200]}

        # Check for simple "no" at start of response or standalone
        if lower_text.startswith("no") or lower_text.startswith("false"):
            return {"ok": False, "reason": response_text[:200]}

        # Check positive patterns
        if any(pattern in lower_text for pattern in positive_patterns):
            return {"ok": True, "reason": response_text[:200]}

        # Default: fail open (allow operation to continue)
        logger.debug(
            f"Could not parse prompt response, defaulting to ok=True: {response_text[:100]}"
        )
        return {"ok": True, "reason": "Could not parse response"}

    async def _execute_single_hook(
        self,
        hook_config: dict[str, Any],
        claude_data: dict[str, Any],
        original_data: dict[str, Any],
        executor: HookExecutor,
    ) -> dict[str, Any]:
        """
        Execute a single hook and return the result fields.

        Args:
            hook_config: Individual hook configuration
            claude_data: Data in Claude Code format for command hooks
            original_data: Original Amplifier event data for prompt hooks
            executor: HookExecutor instance

        Returns:
            HookResult fields dict
        """
        hook_type = hook_config.get("type", "command")

        if hook_type == "command":
            # Execute shell command hook
            command = hook_config.get("command")
            if not command:
                return {"action": "continue"}

            timeout = hook_config.get("timeout", 30.0)
            logger.info(f"Executing command hook: {command}")

            exit_code, stdout, stderr = await executor.execute(command, claude_data, timeout)

            logger.debug(
                f"Hook result: exit_code={exit_code}, stdout={stdout[:100] if stdout else ''}"
            )

            # Translate response
            result_fields = self.translator.from_claude_response(exit_code, stdout, stderr)

        elif hook_type == "prompt":
            # Execute prompt-based hook using LLM
            prompt = hook_config.get("prompt")
            if not prompt:
                return {"action": "continue"}

            logger.info(f"Executing prompt hook: {prompt[:50]}...")

            prompt_result = await self._execute_prompt_hook(prompt, original_data)

            # Translate prompt result to HookResult fields
            # ok=True -> continue, ok=False -> deny
            if prompt_result.get("ok", True):
                result_fields = {"action": "continue"}
                if prompt_result.get("reason"):
                    result_fields["user_message"] = prompt_result["reason"]
            else:
                result_fields = {
                    "action": "deny",
                    "reason": prompt_result.get("reason", "Prompt hook returned ok=false"),
                }

            logger.debug(f"Prompt hook result: {result_fields}")

        else:
            # Unknown hook type, skip
            logger.debug(f"Skipping unknown hook type: {hook_type}")
            return {"action": "continue"}

        return result_fields

    async def _execute_hooks(self, amplifier_event: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute matching hooks for an event.

        Checks both directory-based hooks and skill-scoped hooks.
        Supports parallel execution when matcher group has parallel=true.

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

        # Collect matching groups from all sources (preserving parallel flag)
        matching_groups: list[dict[str, Any]] = []

        # 1. Directory-based hooks (.amplifier/hooks/)
        if claude_event in self.matcher_groups:
            dir_groups = self.matcher_groups[claude_event].get_matching_groups(match_target)
            matching_groups.extend(dir_groups)

        # 2. Skill-scoped hooks (from loaded skills)
        for skill_name, skill_matchers in self.skill_matcher_groups.items():
            if claude_event in skill_matchers:
                skill_groups = skill_matchers[claude_event].get_matching_groups(match_target)
                if skill_groups:
                    logger.debug(f"Found {len(skill_groups)} hook groups from skill '{skill_name}'")
                    matching_groups.extend(skill_groups)

        if not matching_groups:
            logger.debug(f"No matching hooks for {claude_event} with target {match_target}")
            return {"action": "continue"}

        # Count total hooks for logging
        total_hooks = sum(len(g.get("hooks", [])) for g in matching_groups)
        num_groups = len(matching_groups)
        logger.info(f"Found {total_hooks} hooks in {num_groups} groups for {claude_event}")

        # Translate data to Claude Code format
        claude_data = self.translator.to_claude_format(claude_event, data)

        # Get executor
        session_id = data.get("session_id", "unknown")
        executor = self._get_executor(session_id)

        # Process each matcher group
        for matcher_group in matching_groups:
            hooks = matcher_group.get("hooks", [])
            parallel = matcher_group.get("parallel", False)

            if not hooks:
                continue

            if parallel:
                # Run all hooks in this group concurrently
                logger.debug(f"Executing {len(hooks)} hooks in parallel")
                results = await asyncio.gather(
                    *[
                        self._execute_single_hook(hook, claude_data, data, executor)
                        for hook in hooks
                    ],
                    return_exceptions=True,
                )

                # Check for any blocking result
                for result in results:
                    if isinstance(result, BaseException):
                        logger.warning(f"Hook failed with exception: {result}")
                        continue

                    # result is dict[str, Any] after the exception check
                    result_dict: dict[str, Any] = result
                    action = result_dict.get("action", "continue")
                    if action in ("deny", "modify", "inject_context"):
                        logger.info(f"Parallel hook returned blocking action: {action}")
                        return result_dict

            else:
                # Sequential execution (existing behavior)
                for hook_config in hooks:
                    result_fields = await self._execute_single_hook(
                        hook_config, claude_data, data, executor
                    )

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
