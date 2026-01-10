"""
Shell Hooks Module for Amplifier

A module that enables Amplifier to execute shell-based hooks using
Claude Code's proven JSON format for compatibility.
"""

import logging
from collections.abc import Callable
from typing import Any

from amplifier_module_hooks_shell.bridge import ShellHookBridge

__version__ = "0.1.0"
__amplifier_module_type__ = "hook"

logger = logging.getLogger(__name__)

__all__ = [
    "ShellHookBridge",
    "mount",
]


async def mount(coordinator: Any, config: dict[str, Any]) -> Callable | None:
    """
    Mount the shell hooks module.

    This is the entry point called by Amplifier when loading the module.

    Args:
        coordinator: Module coordinator with .hooks registry
        config: Module configuration from bundle YAML

    Returns:
        Cleanup function to unregister hooks
    """
    logger.info("Mounting hooks-shell module")

    # Create bridge with config and coordinator (for provider access)
    bridge = ShellHookBridge(config, coordinator)

    # Register handlers on the coordinator's hook registry
    unregister_fns = []

    # Map Claude Code events to Amplifier events and register handlers
    event_handlers = [
        # Phase 1: Core lifecycle events
        ("tool:pre", bridge.on_tool_pre, "shell-pre-tool"),
        ("tool:post", bridge.on_tool_post, "shell-post-tool"),
        ("prompt:submit", bridge.on_prompt_submit, "shell-prompt-submit"),
        ("session:start", bridge.on_session_start, "shell-session-start"),
        ("session:end", bridge.on_session_end, "shell-session-end"),
        # Phase 1.5: Skill integration events
        ("skill:loaded", bridge.on_skill_loaded, "shell-skill-loaded"),
        ("skill:unloaded", bridge.on_skill_unloaded, "shell-skill-unloaded"),
        # Phase 2: Extended events
        ("prompt:complete", bridge.on_prompt_complete, "shell-stop"),
        ("context:pre_compact", bridge.on_context_pre_compact, "shell-pre-compact"),
        ("approval:required", bridge.on_approval_required, "shell-permission"),
        ("session:resume", bridge.on_session_resume, "shell-session-resume"),
        ("user:notification", bridge.on_user_notification, "shell-notification"),
    ]

    for event, handler, name in event_handlers:
        try:
            unregister = coordinator.hooks.register(
                event=event,
                handler=handler,
                priority=20,  # Run after most native hooks
                name=name,
            )
            unregister_fns.append(unregister)
            logger.debug(f"Registered handler for {event}")
        except Exception as e:
            logger.warning(f"Failed to register handler for {event}: {e}")

    logger.info(f"hooks-shell mounted with {len(unregister_fns)} handlers")

    # Return cleanup function
    def cleanup():
        for unregister in unregister_fns:
            try:
                unregister()
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

    return cleanup
