"""Tests for hook matcher."""

import pytest
from amplifier_hooks_shell.matcher import HookMatcher, MatcherGroup


def test_exact_match():
    """Test exact tool name matching."""
    matcher = HookMatcher("Bash")
    
    assert matcher.matches("Bash")
    assert not matcher.matches("Edit")
    assert not matcher.matches("bash")  # Case sensitive


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
    assert not matcher.matches("Notebook")  # Needs at least one char after


def test_matcher_group():
    """Test MatcherGroup functionality."""
    config = [
        {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "echo 1"}]
        },
        {
            "matcher": "Edit|Write",
            "hooks": [{"type": "command", "command": "echo 2"}]
        }
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
        {
            "matcher": "*",
            "hooks": [{"type": "command", "command": "echo all"}]
        },
        {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "echo bash"}]
        }
    ]
    
    group = MatcherGroup(config)
    
    # Bash should match both
    hooks = group.get_matching_hooks("Bash")
    assert len(hooks) == 2
