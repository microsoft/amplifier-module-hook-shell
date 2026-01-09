"""
Shell Hooks Module for Amplifier

A bridge module that enables Amplifier to execute Claude Code-compatible hooks.
"""

from amplifier_hooks_shell.bridge import ShellHookBridge
from amplifier_hooks_shell.loader import HookConfigLoader
from amplifier_hooks_shell.executor import HookExecutor
from amplifier_hooks_shell.translator import DataTranslator

__version__ = "0.1.0"
__all__ = [
    "ShellHookBridge",
    "HookConfigLoader",
    "HookExecutor",
    "DataTranslator",
    "initialize",
]


def initialize(config: dict, registry):
    """
    Initialize the Claude Code hook bridge.
    
    This is the entry point called by Amplifier when loading the module.
    
    Args:
        config: Module configuration from bundle YAML
        registry: Amplifier HookRegistry instance
    """
    bridge = ShellHookBridge(config)
    bridge.register_hooks(registry)
