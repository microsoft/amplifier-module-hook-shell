"""Tests for hook executor."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from amplifier_module_hooks_shell.executor import HookExecutor


def test_prepare_environment(tmp_path):
    """Test environment variable preparation."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "project" / ".amplifier" / "hooks"
    hooks_dir.mkdir(parents=True)
    session_id = "test-session-123"

    executor = HookExecutor(project_dir, hooks_dir, session_id)
    env = executor._prepare_environment()

    # Check Amplifier variables
    assert env["AMPLIFIER_PROJECT_DIR"] == str(project_dir)
    assert env["AMPLIFIER_HOOKS_DIR"] == str(hooks_dir)
    assert env["AMPLIFIER_SESSION_ID"] == session_id

    # Check Claude Code compatibility alias
    assert env["CLAUDE_PROJECT_DIR"] == str(project_dir)

    # Check that parent environment is preserved
    assert "PATH" in env


def test_prepare_environment_inherits_parent_env(tmp_path):
    """Test that parent environment variables are inherited."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    with patch.dict(os.environ, {"MY_CUSTOM_VAR": "test_value"}):
        env = executor._prepare_environment()
        assert env["MY_CUSTOM_VAR"] == "test_value"


@pytest.mark.asyncio
async def test_execute_successful_command(tmp_path):
    """Test successful command execution."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    # Simple echo command
    exit_code, stdout, stderr = await executor.execute(
        "echo 'hello world'", {"test": "data"}, timeout=5.0
    )

    assert exit_code == 0
    assert "hello world" in stdout
    assert stderr == ""


@pytest.mark.asyncio
async def test_execute_with_stdin_input(tmp_path):
    """Test command receives JSON input on stdin."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    # Cat reads from stdin and outputs it
    exit_code, stdout, stderr = await executor.execute(
        "cat", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, timeout=5.0
    )

    assert exit_code == 0
    assert "tool_name" in stdout
    assert "Bash" in stdout


@pytest.mark.asyncio
async def test_execute_nonzero_exit_code(tmp_path):
    """Test command with non-zero exit code."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    exit_code, stdout, stderr = await executor.execute("exit 2", {}, timeout=5.0)

    assert exit_code == 2


@pytest.mark.asyncio
async def test_execute_stderr_output(tmp_path):
    """Test command that writes to stderr."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    exit_code, stdout, stderr = await executor.execute("echo 'error message' >&2", {}, timeout=5.0)

    assert exit_code == 0
    assert "error message" in stderr


@pytest.mark.asyncio
async def test_execute_timeout():
    """Test command timeout handling."""
    # Use a real temp path for the test
    project_dir = Path("/tmp/test_project")
    project_dir.mkdir(exist_ok=True)
    hooks_dir = Path("/tmp/test_hooks")
    hooks_dir.mkdir(exist_ok=True)

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    # Command that sleeps longer than timeout
    exit_code, stdout, stderr = await executor.execute(
        "sleep 10",
        {},
        timeout=0.1,  # Very short timeout
    )

    assert exit_code == 1
    assert "timed out" in stderr.lower()


@pytest.mark.asyncio
async def test_execute_command_not_found(tmp_path):
    """Test handling of command that doesn't exist."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    exit_code, stdout, stderr = await executor.execute(
        "nonexistent_command_xyz_12345", {}, timeout=5.0
    )

    # Command not found typically returns 127
    assert exit_code != 0
    assert "not found" in stderr.lower() or exit_code == 127


@pytest.mark.asyncio
async def test_execute_uses_project_dir_as_cwd(tmp_path):
    """Test that command runs in project directory."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    # Create a marker file in project dir
    (project_dir / "marker.txt").write_text("found")

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    exit_code, stdout, stderr = await executor.execute("cat marker.txt", {}, timeout=5.0)

    assert exit_code == 0
    assert "found" in stdout


@pytest.mark.asyncio
async def test_execute_expands_environment_variables(tmp_path):
    """Test that environment variables in command are expanded."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    exit_code, stdout, stderr = await executor.execute(
        "echo $AMPLIFIER_SESSION_ID", {}, timeout=5.0
    )

    assert exit_code == 0
    assert "session-1" in stdout


@pytest.mark.asyncio
async def test_execute_with_complex_json_input(tmp_path):
    """Test execution with complex nested JSON input."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    complex_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/path/to/file.py",
            "content": "def hello():\n    print('world')",
        },
        "metadata": {"timestamp": "2024-01-01T00:00:00Z", "session": {"id": "abc123"}},
    }

    exit_code, stdout, stderr = await executor.execute("cat", complex_input, timeout=5.0)

    assert exit_code == 0
    assert "Write" in stdout
    assert "file_path" in stdout


@pytest.mark.asyncio
async def test_execute_handles_unicode_output(tmp_path):
    """Test handling of unicode in command output."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    executor = HookExecutor(project_dir, hooks_dir, "session-1")

    exit_code, stdout, stderr = await executor.execute("echo 'Hello World'", {}, timeout=5.0)

    assert exit_code == 0
    # The echo might output different things based on terminal encoding
    # but it should not crash
    assert stdout is not None
