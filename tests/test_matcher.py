"""Tests for hook matcher."""

from amplifier_module_hooks_shell.matcher import HookMatcher, MatcherGroup


def test_exact_match():
    """Test exact tool name matching (case-insensitive per Claude Code compat)."""
    matcher = HookMatcher("Bash")

    assert matcher.matches("Bash")
    assert not matcher.matches("Edit")
    assert matcher.matches("bash")  # Case-insensitive matching
    assert matcher.matches("BASH")  # Case-insensitive matching


def test_regex_match():
    """Test regex pattern matching."""
    matcher = HookMatcher("Edit|Write")

    assert matcher.matches("Edit")
    assert matcher.matches("Write")
    assert not matcher.matches("Read")


def test_wildcard_match():
    """Test wildcard matching."""
    matcher = HookMatcher("*")

    assert matcher.matches("Bash")
    assert matcher.matches("Edit")
    assert matcher.matches("anything")


def test_empty_pattern_match():
    """Test empty pattern matches all."""
    matcher = HookMatcher("")

    assert matcher.matches("Bash")
    assert matcher.matches("Edit")


def test_complex_regex():
    """Test complex regex patterns."""
    matcher = HookMatcher("Notebook.*")

    assert matcher.matches("NotebookCreate")
    assert matcher.matches("NotebookUpdate")
    assert matcher.matches("Notebook")  # .* matches zero or more chars

    # Use .+ if you need at least one char
    matcher_one_plus = HookMatcher("Notebook.+")
    assert matcher_one_plus.matches("NotebookCreate")
    assert not matcher_one_plus.matches("Notebook")  # .+ requires at least one char


def test_matcher_group():
    """Test MatcherGroup functionality."""
    config = [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo 1"}]},
        {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "echo 2"}]},
    ]

    group = MatcherGroup(config)

    # Bash matches first matcher
    bash_hooks = group.get_matching_hooks("Bash")
    assert len(bash_hooks) == 1
    assert bash_hooks[0]["command"] == "echo 1"

    # Edit matches second matcher
    edit_hooks = group.get_matching_hooks("Edit")
    assert len(edit_hooks) == 1
    assert edit_hooks[0]["command"] == "echo 2"

    # Read matches nothing
    read_hooks = group.get_matching_hooks("Read")
    assert len(read_hooks) == 0


def test_matcher_group_multiple_matches():
    """Test that multiple matchers can match the same tool."""
    config = [
        {"matcher": "*", "hooks": [{"type": "command", "command": "echo all"}]},
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo bash"}]},
    ]

    group = MatcherGroup(config)

    # Bash should match both
    hooks = group.get_matching_hooks("Bash")
    assert len(hooks) == 2


def test_get_matching_groups():
    """Test get_matching_groups returns full matcher config."""
    config = [
        {"matcher": "Bash", "parallel": True, "hooks": [{"type": "command", "command": "echo 1"}]},
        {"matcher": "Edit", "hooks": [{"type": "command", "command": "echo 2"}]},
    ]

    group = MatcherGroup(config)

    # Bash should return the full config including parallel flag
    bash_groups = group.get_matching_groups("Bash")
    assert len(bash_groups) == 1
    assert bash_groups[0]["parallel"] is True
    assert bash_groups[0]["hooks"][0]["command"] == "echo 1"

    # Edit should return config without parallel (not set)
    edit_groups = group.get_matching_groups("Edit")
    assert len(edit_groups) == 1
    assert "parallel" not in edit_groups[0]

    # Read should return empty list
    read_groups = group.get_matching_groups("Read")
    assert len(read_groups) == 0


def test_get_matching_groups_multiple_matches():
    """Test that get_matching_groups returns all matching groups."""
    config = [
        {"matcher": "*", "parallel": False, "hooks": [{"type": "command", "command": "echo all"}]},
        {
            "matcher": "Bash",
            "parallel": True,
            "hooks": [{"type": "command", "command": "echo bash"}],
        },
    ]

    group = MatcherGroup(config)

    # Bash should match both groups
    groups = group.get_matching_groups("Bash")
    assert len(groups) == 2
    assert groups[0]["parallel"] is False
    assert groups[1]["parallel"] is True
