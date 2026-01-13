"""Tests for configuration loader."""

import json

from amplifier_module_hook_shell.loader import HookConfigLoader


def test_load_single_config(tmp_path):
    """Test loading a single hooks.json file."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    config = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo test"}]}
            ]
        }
    }

    (hooks_dir / "hooks.json").write_text(json.dumps(config))

    loader = HookConfigLoader(hooks_dir)
    result = loader.load_all_configs()

    assert "hooks" in result
    assert "PreToolUse" in result["hooks"]


def test_load_multiple_configs(tmp_path):
    """Test loading and merging multiple hook configs."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    # Root config
    root_config = {
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo 1"}]}]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(root_config))

    # Plugin config
    plugin_dir = hooks_dir / "plugin1"
    plugin_dir.mkdir()
    plugin_config = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Edit", "hooks": [{"type": "command", "command": "echo 2"}]}
            ]
        }
    }
    (plugin_dir / "hooks.json").write_text(json.dumps(plugin_config))

    loader = HookConfigLoader(hooks_dir)
    result = loader.load_all_configs()

    assert "PreToolUse" in result["hooks"]
    assert "PostToolUse" in result["hooks"]


def test_merge_same_event(tmp_path):
    """Test that hooks for the same event are merged."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    # Two plugins with same event
    for i in range(2):
        plugin_dir = hooks_dir / f"plugin{i}"
        plugin_dir.mkdir()
        config = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": f"Tool{i}", "hooks": [{"type": "command", "command": f"echo {i}"}]}
                ]
            }
        }
        (plugin_dir / "hooks.json").write_text(json.dumps(config))

    loader = HookConfigLoader(hooks_dir)
    result = loader.load_all_configs()

    # Should have both matchers merged
    assert len(result["hooks"]["PreToolUse"]) == 2


def test_empty_directory(tmp_path):
    """Test loading from empty directory."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    loader = HookConfigLoader(hooks_dir)
    result = loader.load_all_configs()

    assert result == {"hooks": {}}


def test_invalid_json(tmp_path):
    """Test handling of invalid JSON."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    (hooks_dir / "hooks.json").write_text("{ invalid json")

    loader = HookConfigLoader(hooks_dir)
    result = loader.load_all_configs()

    # Should return empty config, not crash
    assert result == {"hooks": {}}
