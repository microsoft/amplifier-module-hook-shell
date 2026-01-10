"""Tests for shell hook bridge."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from amplifier_module_hooks_shell.bridge import ShellHookBridge


@pytest.fixture
def mock_hook_result():
    """Create a mock HookResult class."""

    class MockHookResult:
        def __init__(self, **kwargs):
            self.action = kwargs.get("action", "continue")
            self.reason = kwargs.get("reason")
            self.user_message = kwargs.get("user_message")
            self.context_injection = kwargs.get("context_injection")
            self.modified_input = kwargs.get("modified_input")

    return MockHookResult


def test_bridge_init_no_hooks_directory(tmp_path, monkeypatch):
    """Test bridge initialization when hooks directory doesn't exist."""
    # Change to a directory without hooks
    monkeypatch.chdir(tmp_path)

    bridge = ShellHookBridge({})

    assert bridge.hook_configs == {"hooks": {}}
    assert bridge.matcher_groups == {}
    assert bridge.enabled is True


def test_bridge_init_with_hooks_directory(tmp_path, monkeypatch):
    """Test bridge initialization with hooks directory and config."""
    # Create hooks directory structure
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo test"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    assert "PreToolUse" in bridge.matcher_groups
    assert bridge.enabled is True


def test_bridge_init_disabled(tmp_path, monkeypatch):
    """Test bridge initialization with enabled=False."""
    monkeypatch.chdir(tmp_path)

    bridge = ShellHookBridge({"enabled": False})

    assert bridge.enabled is False


def test_get_executor_creates_new(tmp_path, monkeypatch):
    """Test that _get_executor creates executor on first call."""
    monkeypatch.chdir(tmp_path)

    bridge = ShellHookBridge({})
    assert bridge.executor is None

    executor = bridge._get_executor("session-123")

    assert executor is not None
    assert executor.session_id == "session-123"


def test_get_executor_reuses_existing(tmp_path, monkeypatch):
    """Test that _get_executor reuses existing executor."""
    monkeypatch.chdir(tmp_path)

    bridge = ShellHookBridge({})

    executor1 = bridge._get_executor("session-1")
    executor2 = bridge._get_executor("session-2")

    # Should return same executor instance
    assert executor1 is executor2


@pytest.mark.asyncio
async def test_execute_hooks_disabled(tmp_path, monkeypatch):
    """Test that disabled bridge returns continue."""
    monkeypatch.chdir(tmp_path)

    bridge = ShellHookBridge({"enabled": False})

    result = await bridge._execute_hooks("tool:pre", {"name": "Bash"})

    assert result == {"action": "continue"}


@pytest.mark.asyncio
async def test_execute_hooks_unknown_event(tmp_path, monkeypatch):
    """Test handling of unknown event type."""
    monkeypatch.chdir(tmp_path)

    bridge = ShellHookBridge({})

    result = await bridge._execute_hooks("unknown:event", {"name": "Bash"})

    assert result == {"action": "continue"}


@pytest.mark.asyncio
async def test_execute_hooks_no_matching_hooks(tmp_path, monkeypatch):
    """Test when no hooks match the tool."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Edit", "hooks": [{"type": "command", "command": "echo test"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    # Bash doesn't match Edit matcher
    result = await bridge._execute_hooks("tool:pre", {"name": "Bash"})

    assert result == {"action": "continue"}


@pytest.mark.asyncio
async def test_execute_hooks_matching_hook_returns_continue(tmp_path, monkeypatch):
    """Test matching hook that returns continue."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo ok"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    # Mock the executor to return success
    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    result = await bridge._execute_hooks("tool:pre", {"name": "Bash", "input": {}})

    assert result["action"] == "continue"
    mock_executor.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_hooks_returns_deny(tmp_path, monkeypatch):
    """Test matching hook that returns deny (blocks operation)."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "check.sh"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    # Mock executor to return exit code 2 (deny)
    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(2, "", "Operation blocked"))
    bridge.executor = mock_executor

    result = await bridge._execute_hooks("tool:pre", {"name": "Bash", "input": {}})

    assert result["action"] == "deny"


@pytest.mark.asyncio
async def test_execute_hooks_returns_json_block(tmp_path, monkeypatch):
    """Test matching hook that returns JSON block decision."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write", "hooks": [{"type": "command", "command": "validate.sh"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    # Mock executor to return JSON block response
    json_response = json.dumps(
        {
            "decision": "block",
            "reason": "File is protected",
            "systemMessage": "Cannot modify this file",
        }
    )
    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, json_response, ""))
    bridge.executor = mock_executor

    result = await bridge._execute_hooks("tool:pre", {"name": "Write", "input": {}})

    assert result["action"] == "deny"
    assert result["reason"] == "File is protected"


@pytest.mark.asyncio
async def test_execute_hooks_context_injection(tmp_path, monkeypatch):
    """Test matching hook that injects context."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "lint.sh"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    # Mock executor to return JSON with context injection
    json_response = json.dumps(
        {
            "decision": "approve",
            "contextInjection": "Linting errors found: Line 5 missing semicolon",
            "systemMessage": "Issues detected",
        }
    )
    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, json_response, ""))
    bridge.executor = mock_executor

    result = await bridge._execute_hooks("tool:post", {"name": "Bash", "input": {}, "result": {}})

    assert result["action"] == "inject_context"
    assert "Linting errors" in result["context_injection"]


@pytest.mark.asyncio
async def test_execute_hooks_skips_non_command_hooks(tmp_path, monkeypatch):
    """Test that non-command hook types are skipped."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "script", "script": "test.py"},  # Not command type
                        {"type": "command", "command": "echo ok"},
                    ],
                }
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    await bridge._execute_hooks("tool:pre", {"name": "Bash", "input": {}})

    # Should only call execute once (for the command type hook)
    assert mock_executor.execute.call_count == 1


@pytest.mark.asyncio
async def test_execute_hooks_stops_on_first_deny(tmp_path, monkeypatch):
    """Test that execution stops after first deny result."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": "first.sh"},
                        {"type": "command", "command": "second.sh"},
                    ],
                }
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    # First hook returns deny
    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(2, "", "Blocked"))
    bridge.executor = mock_executor

    result = await bridge._execute_hooks("tool:pre", {"name": "Bash", "input": {}})

    # Should only call first hook, not second
    assert mock_executor.execute.call_count == 1
    assert result["action"] == "deny"


@pytest.mark.asyncio
async def test_execute_hooks_with_custom_timeout(tmp_path, monkeypatch):
    """Test hook execution with custom timeout from config."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "slow.sh", "timeout": 60.0}],
                }
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    await bridge._execute_hooks("tool:pre", {"name": "Bash", "input": {}})

    # Check that timeout was passed to executor
    call_args = mock_executor.execute.call_args
    assert call_args[0][2] == 60.0  # Third positional arg is timeout


@pytest.mark.asyncio
async def test_on_tool_pre_handler(tmp_path, monkeypatch, mock_hook_result):
    """Test on_tool_pre event handler."""
    monkeypatch.chdir(tmp_path)

    # HookResult is imported locally in each method, so patch at amplifier_core.models
    with patch("amplifier_core.models.HookResult", mock_hook_result):
        with patch.object(
            ShellHookBridge, "_execute_hooks", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"action": "continue"}

            bridge = ShellHookBridge({})
            result = await bridge.on_tool_pre("tool:pre", {"name": "Bash"})

            assert result.action == "continue"
            mock_execute.assert_called_once_with("tool:pre", {"name": "Bash"})


@pytest.mark.asyncio
async def test_on_tool_post_handler(tmp_path, monkeypatch, mock_hook_result):
    """Test on_tool_post event handler."""
    monkeypatch.chdir(tmp_path)

    with patch("amplifier_core.models.HookResult", mock_hook_result):
        with patch.object(
            ShellHookBridge, "_execute_hooks", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"action": "continue"}

            bridge = ShellHookBridge({})
            result = await bridge.on_tool_post("tool:post", {"name": "Bash", "result": {}})

            assert result.action == "continue"
            mock_execute.assert_called_once()


@pytest.mark.asyncio
async def test_on_prompt_submit_handler(tmp_path, monkeypatch, mock_hook_result):
    """Test on_prompt_submit event handler."""
    monkeypatch.chdir(tmp_path)

    with patch("amplifier_core.models.HookResult", mock_hook_result):
        with patch.object(
            ShellHookBridge, "_execute_hooks", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"action": "continue"}

            bridge = ShellHookBridge({})
            result = await bridge.on_prompt_submit("prompt:submit", {"prompt": "hello"})

            assert result.action == "continue"
            mock_execute.assert_called_once_with("prompt:submit", {"prompt": "hello"})


@pytest.mark.asyncio
async def test_on_session_start_handler(tmp_path, monkeypatch, mock_hook_result):
    """Test on_session_start event handler."""
    monkeypatch.chdir(tmp_path)

    with patch("amplifier_core.models.HookResult", mock_hook_result):
        with patch.object(
            ShellHookBridge, "_execute_hooks", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"action": "continue"}

            bridge = ShellHookBridge({})
            result = await bridge.on_session_start("session:start", {"session_id": "123"})

            assert result.action == "continue"


@pytest.mark.asyncio
async def test_on_session_end_handler(tmp_path, monkeypatch, mock_hook_result):
    """Test on_session_end event handler."""
    monkeypatch.chdir(tmp_path)

    with patch("amplifier_core.models.HookResult", mock_hook_result):
        with patch.object(
            ShellHookBridge, "_execute_hooks", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"action": "continue"}

            bridge = ShellHookBridge({})
            result = await bridge.on_session_end("session:end", {"session_id": "123"})

            assert result.action == "continue"


def test_claude_event_map():
    """Test that event map contains expected mappings."""
    expected_mappings = {
        "tool:pre": "PreToolUse",
        "tool:post": "PostToolUse",
        "prompt:submit": "UserPromptSubmit",
        "session:start": "SessionStart",
        "session:end": "SessionEnd",
    }

    assert ShellHookBridge.CLAUDE_EVENT_MAP == expected_mappings


@pytest.mark.asyncio
async def test_execute_hooks_extracts_tool_name_variants(tmp_path, monkeypatch):
    """Test that tool name is extracted from both 'name' and 'tool_name' fields."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo ok"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    # Test with 'tool_name' field
    await bridge._execute_hooks("tool:pre", {"tool_name": "Bash", "input": {}})
    assert mock_executor.execute.call_count == 1

    # Reset mock
    mock_executor.execute.reset_mock()

    # Test with 'name' field
    await bridge._execute_hooks("tool:pre", {"name": "Bash", "input": {}})
    assert mock_executor.execute.call_count == 1
