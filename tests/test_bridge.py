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
    # Phase 1 events
    expected_mappings = {
        "tool:pre": "PreToolUse",
        "tool:post": "PostToolUse",
        "prompt:submit": "UserPromptSubmit",
        "session:start": "SessionStart",
        "session:end": "SessionEnd",
        # Phase 2 events
        "prompt:complete": "Stop",
        "context:pre_compact": "PreCompact",
        "approval:required": "PermissionRequest",
        "session:resume": "SessionStart",
        "user:notification": "Notification",
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


# --- Phase 2 Event Handler Tests ---


@pytest.mark.asyncio
async def test_on_prompt_complete_handler(tmp_path, monkeypatch):
    """Test that prompt:complete (Stop) events are handled correctly."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "Stop": [{"matcher": ".*", "hooks": [{"type": "command", "command": "echo stop"}]}]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    result = await bridge.on_prompt_complete("prompt:complete", {})
    assert result.action == "continue"


@pytest.mark.asyncio
async def test_on_context_pre_compact_handler(tmp_path, monkeypatch):
    """Test that context:pre_compact (PreCompact) events are handled correctly."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PreCompact": [
                {"matcher": ".*", "hooks": [{"type": "command", "command": "echo compact"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    result = await bridge.on_context_pre_compact("context:pre_compact", {})
    assert result.action == "continue"


@pytest.mark.asyncio
async def test_on_approval_required_handler(tmp_path, monkeypatch):
    """Test that approval:required (PermissionRequest) events are handled correctly."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "PermissionRequest": [
                {"matcher": ".*", "hooks": [{"type": "command", "command": "echo approve"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    result = await bridge.on_approval_required("approval:required", {"operation": "write"})
    assert result.action == "continue"


@pytest.mark.asyncio
async def test_on_user_notification_handler(tmp_path, monkeypatch):
    """Test that user:notification (Notification) events are handled correctly."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "Notification": [
                {"matcher": ".*", "hooks": [{"type": "command", "command": "echo notify"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    result = await bridge.on_user_notification("user:notification", {"message": "test"})
    assert result.action == "continue"


@pytest.mark.asyncio
async def test_session_start_trigger_matching(tmp_path, monkeypatch):
    """Test that SessionStart events match on trigger field."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    # Hook that only matches "resume" trigger
    config = {
        "hooks": {
            "SessionStart": [
                {"matcher": "resume", "hooks": [{"type": "command", "command": "echo resume"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    # Should NOT match - trigger is "startup"
    await bridge._execute_hooks("session:start", {"trigger": "startup"})
    assert mock_executor.execute.call_count == 0

    # Should match - trigger is "resume"
    await bridge._execute_hooks("session:start", {"trigger": "resume"})
    assert mock_executor.execute.call_count == 1


@pytest.mark.asyncio
async def test_session_resume_adds_trigger(tmp_path, monkeypatch):
    """Test that session:resume events add trigger=resume to data."""
    hooks_dir = tmp_path / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)

    config = {
        "hooks": {
            "SessionStart": [
                {"matcher": "resume", "hooks": [{"type": "command", "command": "echo resume"}]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    monkeypatch.chdir(tmp_path)
    bridge = ShellHookBridge({})

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value=(0, "", ""))
    bridge.executor = mock_executor

    # on_session_resume should add trigger=resume
    result = await bridge.on_session_resume("session:resume", {"session_id": "test"})
    assert result.action == "continue"
    # The hook should have been executed since trigger=resume matches
    assert mock_executor.execute.call_count == 1


# --- Phase 2.5 Prompt Hook Tests ---


class TestExpandArguments:
    """Tests for $ARGUMENTS placeholder expansion."""

    def test_no_placeholder(self, tmp_path, monkeypatch):
        """Test that prompts without $ARGUMENTS are returned unchanged."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        prompt = "Is this task complete?"
        result = bridge._expand_arguments(prompt, {"prompt": "test"})

        assert result == prompt

    def test_expand_with_prompt(self, tmp_path, monkeypatch):
        """Test expansion with user prompt data."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        prompt = "The task was: $ARGUMENTS"
        result = bridge._expand_arguments(prompt, {"prompt": "Fix the bug in auth.py"})

        assert "Fix the bug in auth.py" in result
        assert "$ARGUMENTS" not in result

    def test_expand_with_tool_data(self, tmp_path, monkeypatch):
        """Test expansion with tool name and input."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        prompt = "Review this: $ARGUMENTS"
        data = {"name": "Bash", "input": {"command": "ls -la"}}
        result = bridge._expand_arguments(prompt, data)

        assert "Bash" in result
        assert "ls -la" in result

    def test_expand_with_result_truncation(self, tmp_path, monkeypatch):
        """Test that long results are truncated."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        prompt = "Evaluate: $ARGUMENTS"
        long_result = "x" * 1000
        data = {"result": {"output": long_result}}
        result = bridge._expand_arguments(prompt, data)

        assert "..." in result  # Should be truncated
        assert len(result) < 1000  # Much shorter than original


class TestParsePromptResponse:
    """Tests for LLM response parsing."""

    def test_parse_json_ok_true(self, tmp_path, monkeypatch):
        """Test parsing JSON with ok=true."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        response = '{"ok": true, "reason": "Task is complete"}'
        result = bridge._parse_prompt_response(response)

        assert result["ok"] is True
        assert result["reason"] == "Task is complete"

    def test_parse_json_ok_false(self, tmp_path, monkeypatch):
        """Test parsing JSON with ok=false."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        response = '{"ok": false, "reason": "More work needed"}'
        result = bridge._parse_prompt_response(response)

        assert result["ok"] is False
        assert result["reason"] == "More work needed"

    def test_parse_json_in_markdown(self, tmp_path, monkeypatch):
        """Test parsing JSON wrapped in markdown code blocks."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        response = """Here is my response:
```json
{"ok": false, "reason": "Not done yet"}
```"""
        result = bridge._parse_prompt_response(response)

        assert result["ok"] is False

    def test_parse_string_ok_values(self, tmp_path, monkeypatch):
        """Test parsing string representations of ok value."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        # Test "true" string
        result = bridge._parse_prompt_response('{"ok": "true", "reason": "done"}')
        assert result["ok"] is True

        # Test "yes" string
        result = bridge._parse_prompt_response('{"ok": "yes", "reason": "done"}')
        assert result["ok"] is True

        # Test "false" string
        result = bridge._parse_prompt_response('{"ok": "false", "reason": "not done"}')
        assert result["ok"] is False

    def test_parse_simple_yes(self, tmp_path, monkeypatch):
        """Test parsing simple 'yes' response."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        result = bridge._parse_prompt_response("Yes, the task is complete.")

        assert result["ok"] is True

    def test_parse_simple_no(self, tmp_path, monkeypatch):
        """Test parsing simple 'no' response."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        result = bridge._parse_prompt_response("No, there's more work to do.")

        assert result["ok"] is False

    def test_parse_incomplete_keyword(self, tmp_path, monkeypatch):
        """Test parsing response with 'incomplete' keyword."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        result = bridge._parse_prompt_response("The task is incomplete.")

        assert result["ok"] is False

    def test_parse_default_on_ambiguous(self, tmp_path, monkeypatch):
        """Test that ambiguous responses default to ok=True (fail open)."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        result = bridge._parse_prompt_response("I'm not sure what you're asking.")

        assert result["ok"] is True  # Fail open


class TestExecutePromptHook:
    """Tests for prompt hook execution."""

    @pytest.mark.asyncio
    async def test_no_coordinator(self, tmp_path, monkeypatch):
        """Test prompt hook with no coordinator returns ok=True."""
        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})  # No coordinator

        result = await bridge._execute_prompt_hook("Is this done?", {})

        assert result["ok"] is True
        assert "No provider" in result["reason"]

    @pytest.mark.asyncio
    async def test_no_providers(self, tmp_path, monkeypatch):
        """Test prompt hook with no providers returns ok=True."""
        from unittest.mock import Mock

        monkeypatch.chdir(tmp_path)

        mock_coordinator = Mock()
        mock_coordinator.get = Mock(return_value={})  # Empty providers

        bridge = ShellHookBridge({}, mock_coordinator)

        result = await bridge._execute_prompt_hook("Is this done?", {})

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_provider_returns_ok_true(self, tmp_path, monkeypatch):
        """Test prompt hook with provider returning ok=true."""
        from unittest.mock import Mock

        monkeypatch.chdir(tmp_path)

        # Mock response - use Mock for attributes, not AsyncMock
        mock_content_block = Mock()
        mock_content_block.text = '{"ok": true, "reason": "Complete"}'
        mock_response = Mock()
        mock_response.content = [mock_content_block]

        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        # Mock coordinator - get is synchronous
        mock_coordinator = Mock()
        mock_coordinator.get = Mock(return_value={"default": mock_provider})

        bridge = ShellHookBridge({}, mock_coordinator)

        with patch("amplifier_core.message_models.ChatRequest"):
            with patch("amplifier_core.message_models.Message"):
                with patch("amplifier_core.message_models.TextBlock"):
                    result = await bridge._execute_prompt_hook("Is this done?", {})

        assert result["ok"] is True
        assert result["reason"] == "Complete"

    @pytest.mark.asyncio
    async def test_provider_returns_ok_false(self, tmp_path, monkeypatch):
        """Test prompt hook with provider returning ok=false."""
        from unittest.mock import Mock

        monkeypatch.chdir(tmp_path)

        # Mock response - use Mock for attributes
        mock_content_block = Mock()
        mock_content_block.text = '{"ok": false, "reason": "Not done"}'
        mock_response = Mock()
        mock_response.content = [mock_content_block]

        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        # Mock coordinator - get is synchronous
        mock_coordinator = Mock()
        mock_coordinator.get = Mock(return_value={"default": mock_provider})

        bridge = ShellHookBridge({}, mock_coordinator)

        with patch("amplifier_core.message_models.ChatRequest"):
            with patch("amplifier_core.message_models.Message"):
                with patch("amplifier_core.message_models.TextBlock"):
                    result = await bridge._execute_prompt_hook("Is this done?", {})

        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_provider_error_defaults_ok(self, tmp_path, monkeypatch):
        """Test that provider errors default to ok=True (fail open)."""
        from unittest.mock import Mock

        monkeypatch.chdir(tmp_path)

        # Mock provider that raises
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(side_effect=Exception("Provider error"))

        # Mock coordinator - get is synchronous
        mock_coordinator = Mock()
        mock_coordinator.get = Mock(return_value={"default": mock_provider})

        bridge = ShellHookBridge({}, mock_coordinator)

        with patch("amplifier_core.message_models.ChatRequest"):
            with patch("amplifier_core.message_models.Message"):
                with patch("amplifier_core.message_models.TextBlock"):
                    result = await bridge._execute_prompt_hook("Is this done?", {})

        assert result["ok"] is True
        assert "error" in result["reason"].lower()


class TestPromptHookExecution:
    """Tests for prompt hook execution in _execute_hooks."""

    @pytest.mark.asyncio
    async def test_execute_prompt_hook_ok_true(self, tmp_path, monkeypatch):
        """Test that prompt hook with ok=true returns continue."""
        hooks_dir = tmp_path / ".amplifier" / "hooks"
        hooks_dir.mkdir(parents=True)

        config = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "prompt",
                                "prompt": "Is the task complete? $ARGUMENTS",
                            }
                        ],
                    }
                ]
            }
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(config))

        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        # Mock _execute_prompt_hook to return ok=True
        with patch.object(bridge, "_execute_prompt_hook", new_callable=AsyncMock) as mock_prompt:
            mock_prompt.return_value = {"ok": True, "reason": "Complete"}

            result = await bridge._execute_hooks("prompt:complete", {"prompt": "fix bug"})

        assert result["action"] == "continue"

    @pytest.mark.asyncio
    async def test_execute_prompt_hook_ok_false(self, tmp_path, monkeypatch):
        """Test that prompt hook with ok=false returns deny."""
        hooks_dir = tmp_path / ".amplifier" / "hooks"
        hooks_dir.mkdir(parents=True)

        config = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "prompt",
                                "prompt": "Is the task complete?",
                            }
                        ],
                    }
                ]
            }
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(config))

        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        # Mock _execute_prompt_hook to return ok=False
        with patch.object(bridge, "_execute_prompt_hook", new_callable=AsyncMock) as mock_prompt:
            mock_prompt.return_value = {"ok": False, "reason": "Not done yet"}

            result = await bridge._execute_hooks("prompt:complete", {})

        assert result["action"] == "deny"
        assert result["reason"] == "Not done yet"

    @pytest.mark.asyncio
    async def test_mixed_command_and_prompt_hooks(self, tmp_path, monkeypatch):
        """Test execution with both command and prompt hooks."""
        hooks_dir = tmp_path / ".amplifier" / "hooks"
        hooks_dir.mkdir(parents=True)

        config = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "echo ok"},
                            {"type": "prompt", "prompt": "Allow this?"},
                        ],
                    }
                ]
            }
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(config))

        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        # Mock command executor
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=(0, "", ""))
        bridge.executor = mock_executor

        # Mock prompt hook
        with patch.object(bridge, "_execute_prompt_hook", new_callable=AsyncMock) as mock_prompt:
            mock_prompt.return_value = {"ok": True, "reason": "Allowed"}

            result = await bridge._execute_hooks("tool:pre", {"name": "Bash", "input": {}})

        # Both hooks should be called
        assert mock_executor.execute.call_count == 1
        assert mock_prompt.call_count == 1
        assert result["action"] == "continue"

    @pytest.mark.asyncio
    async def test_prompt_hook_without_prompt_field(self, tmp_path, monkeypatch):
        """Test that prompt hooks without prompt field are skipped."""
        hooks_dir = tmp_path / ".amplifier" / "hooks"
        hooks_dir.mkdir(parents=True)

        config = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "prompt"},  # Missing prompt field
                        ],
                    }
                ]
            }
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(config))

        monkeypatch.chdir(tmp_path)
        bridge = ShellHookBridge({})

        result = await bridge._execute_hooks("prompt:complete", {})

        assert result["action"] == "continue"
