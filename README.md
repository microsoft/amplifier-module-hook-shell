# Shell Hooks Module for Amplifier

Add shell-based extensibility to Amplifier with hooks that execute at lifecycle points. Uses Claude Code's proven hook format for compatibility with their ecosystem.

## Overview

This module enables shell command hooks in Amplifier projects. Hooks can validate, format, block, or inject context into agent execution—all through simple shell scripts.

**What it provides:**
- Shell-based hooks at tool and session lifecycle points
- Regex pattern matching for selective execution
- Parallel hook execution for performance
- Prompt-based hooks for LLM evaluation
- Skill-scoped hooks (hooks embedded in SKILL.md)
- Security controls (timeouts, exit code handling)
- Claude Code format compatibility

## Quick Start

### Installation

Add to your Amplifier bundle:

```yaml
# bundle.yaml
hooks:
  - module: hook-shell
    source: git+https://github.com/microsoft/amplifier-module-hook-shell@main
```

### Create Your First Hook

1. **Create hooks directory:**
```bash
mkdir -p .amplifier/hooks
```

2. **Create `hooks.json`:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Bash command detected' >&2 && exit 0"
          }
        ]
      }
    ]
  }
}
```

That's it! The hook will run before every Bash tool execution.

## Hook Format

Uses Claude Code's JSON hook format for compatibility:

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "parallel": false,
        "hooks": [
          {
            "type": "command",
            "command": "path/to/script.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

| Field | Description |
|-------|-------------|
| `matcher` | Regex pattern: `"Bash"`, `"Edit\|Write"`, `".*"` |
| `parallel` | Run hooks concurrently (default: `false`) |
| `type` | `"command"` or `"prompt"` |
| `command` | Shell command or script path |
| `timeout` | Seconds before timeout (default: 30) |

## Supported Events

| Event | When It Fires | Can Block | Context Injection |
|-------|---------------|-----------|-------------------|
| `PreToolUse` | Before tool execution | Yes | Yes |
| `PostToolUse` | After tool completion | No | Yes |
| `UserPromptSubmit` | User submits prompt | Yes | Yes |
| `Notification` | Agent sends notification | No | No |
| `Stop` | Agent stops execution | No | No |
| `SubagentStart` | Subagent spawned | No | No |
| `SubagentStop` | Subagent completed | No | No |
| `SessionStart` | Session initialization | No | No |
| `SessionEnd` | Session cleanup | No | No |

## Hook Input/Output

### Input (stdin)
Hooks receive JSON on stdin:

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la",
    "description": "List files"
  },
  "session_id": "abc-123",
  "timestamp": "2026-01-09T20:15:19Z"
}
```

### Output
**Exit codes:**
- `0` - Success, allow operation
- `2` - Block operation (blocking events only)
- Other - Error (treated as allow with warning)

**JSON output (optional, on stdout):**
```json
{
  "decision": "approve",
  "reason": "Explanation",
  "systemMessage": "Message to user",
  "contextInjection": "Feedback to inject into agent context"
}
```

## Parallel Execution

Run multiple hooks concurrently for better performance:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ".*",
        "parallel": true,
        "hooks": [
          {"type": "command", "command": "./notify-slack.sh"},
          {"type": "command", "command": "./update-metrics.sh"},
          {"type": "command", "command": "./sync-logs.sh"}
        ]
      }
    ]
  }
}
```

**Parallel behavior:**
- All hooks start simultaneously
- For blocking events: short-circuits on first `block` decision
- Exceptions are caught and logged, don't fail the group
- Default is sequential (`parallel: false`)

## Prompt-Based Hooks

Use LLM evaluation for complex decisions:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Review this bash command for security issues. Output JSON with 'decision' (approve/block) and 'reason'.",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

**Prompt hooks:**
- Send tool context + your prompt to the configured LLM
- LLM returns JSON with decision
- Useful for nuanced evaluation (security review, code quality)
- Higher latency than command hooks—use selectively

**Note:** Prompt hooks require provider configuration. Currently uses the session's default provider. A future enhancement will allow specifying a fast/cheap model override.

## Skill-Scoped Hooks

Embed hooks directly in skill definitions:

```markdown
---
name: python-guardian
description: Enforces Python best practices
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "ruff check --fix $FILE_PATH"
---

# Python Guardian

This skill enforces Python code quality...
```

**How it works:**
1. When a skill is loaded, its hooks are registered automatically
2. Hooks only active while skill is in context
3. Keeps enforcement rules with the skill that defines them

Requires `amplifier-module-tool-skills` with hooks support.

## Environment Variables

Hooks have access to:

| Variable | Description |
|----------|-------------|
| `AMPLIFIER_PROJECT_DIR` | Project root |
| `AMPLIFIER_HOOKS_DIR` | `.amplifier/hooks/` directory |
| `AMPLIFIER_SESSION_ID` | Current session ID |

## Example Hooks

See `examples/hooks/` for complete examples:

### bash-validator
Blocks dangerous bash commands:
```bash
cp -r examples/hooks/bash-validator .amplifier/hooks/
```

### auto-formatter
Formats code after editing (Python, JS, Go, Rust):
```bash
cp -r examples/hooks/auto-formatter .amplifier/hooks/
```

### linter
Runs linters and injects feedback:
```bash
cp -r examples/hooks/linter .amplifier/hooks/
```

## Claude Code Compatibility

This module uses Claude Code's hook format, making it compatible with:
- Claude Code plugins (copy hooks directory)
- Shared hook scripts from their ecosystem
- Existing Claude Code hook documentation

**Note**: We use `.amplifier/hooks/` instead of `.claude/hooks/` for Amplifier-native integration.

## Security Considerations

**Hooks run with your user permissions.** Only install hooks from trusted sources.

**Built-in protections:**
- Timeout enforcement (default 30s)
- Process isolation (subprocess execution)
- No privilege escalation
- Exit code validation

**Best practices:**
- Review hook code before installation
- Use timeouts on all hooks
- Test in non-production first
- Use specific matchers (avoid `.*` when possible)

## Documentation

- [Complete Specification](SPEC.md) - Architecture and design
- [Example Hooks](examples/hooks/) - Working examples

## Contributing

Contributions welcome! Please ensure alignment with:
- Shell-first approach (not Python)
- Claude Code format compatibility
- Security-conscious design
- Amplifier's modular philosophy

## License

MIT License - See LICENSE file for details

## Status

**Implemented:**
- Core command hooks with exit codes and JSON responses
- Extended lifecycle events (Notification, Stop, Subagent*)
- Prompt-based hooks (LLM evaluation)
- Parallel hook execution
- Skill-scoped hooks integration

**Future (post-upstream):**
- CLI commands (`amplifier hooks install/list/enable/disable`)
- Hook migration tools (Claude Code to Amplifier)
- Plugin package format and marketplace
