"""Tests for data translator."""

from amplifier_module_hook_shell.translator import DataTranslator


def test_translate_pre_tool_use():
    """Test translating PreToolUse event data."""
    translator = DataTranslator()

    amplifier_data = {"name": "Bash", "input": {"command": "ls -la", "description": "List files"}}

    result = translator.to_claude_format("PreToolUse", amplifier_data)

    assert result["tool_name"] == "Bash"
    assert result["tool_input"]["command"] == "ls -la"
    assert "timestamp" in result


def test_translate_post_tool_use():
    """Test translating PostToolUse event data."""
    translator = DataTranslator()

    amplifier_data = {
        "name": "Bash",
        "input": {"command": "ls"},
        "result": {"stdout": "file1.txt\nfile2.txt", "returncode": 0},
    }

    result = translator.to_claude_format("PostToolUse", amplifier_data)

    assert result["tool_name"] == "Bash"
    assert result["tool_result"]["stdout"] == "file1.txt\nfile2.txt"


def test_exit_code_continue():
    """Test exit code 0 translates to continue."""
    translator = DataTranslator()

    result = translator.from_claude_response(0, "", "")

    assert result["action"] == "continue"


def test_exit_code_deny():
    """Test exit code 2 translates to deny."""
    translator = DataTranslator()

    result = translator.from_claude_response(2, "", "Operation blocked")

    assert result["action"] == "deny"
    assert "blocked" in result["reason"].lower()


def test_json_block_decision():
    """Test JSON block decision."""
    translator = DataTranslator()

    json_output = """
    {
        "decision": "block",
        "reason": "File is protected",
        "systemMessage": "Cannot modify this file"
    }
    """

    result = translator.from_claude_response(0, json_output, "")

    assert result["action"] == "deny"
    assert result["reason"] == "File is protected"
    assert result["user_message"] == "Cannot modify this file"


def test_json_context_injection():
    """Test JSON context injection."""
    translator = DataTranslator()

    json_output = """
    {
        "decision": "approve",
        "contextInjection": "Linting errors found: Line 5: Missing semicolon",
        "systemMessage": "Linting issues detected"
    }
    """

    result = translator.from_claude_response(0, json_output, "")

    assert result["action"] == "inject_context"
    assert "Linting errors" in result["context_injection"]
    assert result["user_message"] == "Linting issues detected"


def test_json_approve():
    """Test JSON approve decision."""
    translator = DataTranslator()

    json_output = """
    {
        "decision": "approve",
        "systemMessage": "All checks passed"
    }
    """

    result = translator.from_claude_response(0, json_output, "")

    assert result["action"] == "continue"
    assert result["user_message"] == "All checks passed"


def test_invalid_json():
    """Test handling of invalid JSON."""
    translator = DataTranslator()

    result = translator.from_claude_response(0, "{ invalid json", "")

    # Should default to continue, not crash
    assert result["action"] == "continue"
