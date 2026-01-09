"""
Main bridge module for Claude Code hooks.

Coordinates loading, matching, execution, and translation of hooks.
"""

import os
from pathlib import Path
from typing import Any, Callable

from amplifier_hooks_shell.loader import HookConfigLoader
from amplifier_hooks_shell.executor import HookExecutor
from amplifier_hooks_shell.translator import DataTranslator
from amplifier_hooks_shell.matcher import MatcherGroup


class ClaudeCodeHookBridge:
    """Bridge that executes Claude Code hooks in Amplifier."""
    
    # Map Claude Code events to Amplifier events
    EVENT_MAP = {
        "PreToolUse": "tool:pre",
        "PostToolUse": "tool:post",
        "UserPromptSubmit": "prompt:submit",
        "SessionStart": "session:start",
        "SessionEnd": "session:end",
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
            print(f"Info: Hooks directory not found at {hooks_dir}")
            self.hook_configs = {"hooks": {}}
        else:
            # Load configurations
            loader = HookConfigLoader(hooks_dir)
            self.hook_configs = loader.load_all_configs()
        
        # Initialize components
        self.project_dir = project_dir
        self.hooks_dir = hooks_dir
        self.translator = DataTranslator()
        
        # Create matcher groups for each event
        self.matcher_groups: dict[str, MatcherGroup] = {}
        for event_name, matchers_config in self.hook_configs.get("hooks", {}).items():
            self.matcher_groups[event_name] = MatcherGroup(matchers_config)
    
    def register_hooks(self, registry) -> None:
        """
        Register all Claude Code hooks with Amplifier.
        
        Args:
            registry: Amplifier HookRegistry instance
        """
        if not self.enabled:
            print("Claude Code hook bridge is disabled")
            return
        
        # Get session ID from registry if available
        session_id = getattr(registry, 'session_id', 'unknown')
        
        # Create executor
        self.executor = HookExecutor(self.project_dir, self.hooks_dir, session_id)
        
        # Register handlers for each mapped event
        for claude_event, amplifier_event in self.EVENT_MAP.items():
            if claude_event in self.matcher_groups:
                handler = self._create_handler(claude_event)
                registry.register(
                    event=amplifier_event,
                    handler=handler,
                    priority=20,  # Run after most native hooks
                    name=f"claude_code_{claude_event}"
                )
    
    def _create_handler(self, claude_event: str) -> Callable:
        """
        Create an Amplifier hook handler for a Claude Code event.
        
        Args:
            claude_event: Claude Code event name
            
        Returns:
            Async handler function
        """
        matcher_group = self.matcher_groups[claude_event]
        
        async def handler(event: str, data: dict[str, Any]):
            """Hook handler that executes matching Claude Code hooks."""
            from amplifier_core.models import HookResult
            
            # Extract tool name for matching
            tool_name = data.get("name", "")
            
            # Get matching hooks
            matching_hooks = matcher_group.get_matching_hooks(tool_name)
            
            if not matching_hooks:
                return HookResult(action="continue")
            
            # Translate data to Claude Code format
            claude_data = self.translator.to_claude_format(claude_event, data)
            
            # Execute all matching hooks
            # For now, execute sequentially and use first blocking result
            for hook_config in matching_hooks:
                if hook_config.get("type") != "command":
                    # Skip non-command hooks (prompt-based is Phase 2)
                    continue
                
                command = hook_config["command"]
                timeout = hook_config.get("timeout", 30.0)
                
                # Execute hook
                exit_code, stdout, stderr = await self.executor.execute(
                    command, claude_data, timeout
                )
                
                # Translate response
                result_fields = self.translator.from_claude_response(
                    exit_code, stdout, stderr
                )
                
                # If this hook blocks or modifies, return immediately
                action = result_fields.get("action", "continue")
                if action in ("deny", "modify", "inject_context"):
                    return HookResult(**result_fields)
            
            # All hooks passed
            return HookResult(action="continue")
        
        return handler
