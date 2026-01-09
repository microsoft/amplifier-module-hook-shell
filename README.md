# Shell Hooks Module for Amplifier

Add shell-based extensibility to Amplifier with hooks that execute at lifecycle points. Uses Claude Code's proven hook format for compatibility with their ecosystem.

## Overview

This module enables shell command hooks in Amplifier projects. Hooks can validate, format, block, or inject context into agent execution—all through simple shell scripts.

**What it provides:**
- 🔧 Shell-based hooks at tool and session lifecycle points
- 🎯 Regex pattern matching for selective execution
- 🔒 Security controls (timeouts, exit code handling)
- 🔌 Claude Code format compatibility (leverage their plugin ecosystem)
- 🏗️ Foundation-ready (designed for inclusion in amplifier-foundation)

## Why Shell Hooks?

Shell hooks complement Python hooks by providing:
- **Simplicity** - No Python coding required
- **Portability** - Use any language/tool (bash, python scripts, system commands)
- **Reusability** - Share hooks across projects as plugins
- **Ecosystem** - Leverage Claude Code's hook ecosystem

## Quick Start

### Installation

Add to your Amplifier bundle:

```yaml
# bundle.yaml
hooks:
  - module: hooks-shell
    source: git+https://github.com/robotdad/amplifier-module-hooks-shell@main
```

### Create Your First Hook

1. **Create hooks directory:**
```bash
mkdir -p .amplifier/hooks/my-hook
```

2. **Create `hooks.json`:**
```json
{
  "description": "Log bash commands",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${AMPLIFIER_HOOKS_DIR}/my-hook/log.sh"
          }
        ]
      }
    ]
  }
}
```

3. **Create `log.sh`:**
```bash
#!/bin/bash
jq -r '.tool_input.command' >> bash-commands.log
```

4. **Make executable:**
```bash
chmod +x .amplifier/hooks/my-hook/log.sh
```

## Hook Format

Uses Claude Code's JSON hook format for compatibility:

```json
{
  "description": "Hook description",
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",  // Regex: "Bash", "Edit|Write", "*"
        "hooks": [
          {
            "type": "command",
            "command": "path/to/script.sh",
            "timeout": 30  // optional, seconds
          }
        ]
      }
    ]
  }
}
```

## Supported Events

| Event | When It Fires | Can Block |
|-------|---------------|-----------|
| `PreToolUse` | Before tool execution | ✅ Yes |
| `PostToolUse` | After tool completion | ❌ No |
| `UserPromptSubmit` | User submits prompt | ✅ Yes |
| `SessionStart` | Session initialization | ❌ No |
| `SessionEnd` | Session cleanup | ❌ No |

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
  "timestamp": "2026-01-09T20:15:19Z"
}
```

### Output
**Exit codes:**
- `0` - Success, allow operation
- `2` - Block operation
- Other - Error (treated as allow with warning)

**JSON output (optional, on stdout):**
```json
{
  "decision": "approve|block",
  "reason": "Explanation",
  "systemMessage": "Message to user",
  "contextInjection": "Feedback to inject into agent context"
}
```

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

## Use in Skills

Skills can reference hooks for enforcement. Example in a `SKILL.md`:

```markdown
## Enforcement

For automatic Python linting, install the linter hook:

\`\`\`bash
# In your project
mkdir -p .amplifier/hooks
cp -r /path/to/linter .amplifier/hooks/
\`\`\`

Configure in your bundle:

\`\`\`yaml
hooks:
  - module: hooks-shell
    source: git+https://github.com/robotdad/amplifier-module-hooks-shell@main
\`\`\`
```

## Security Considerations

⚠️ **Hooks run with your user permissions.** Only install hooks from trusted sources.

**Built-in protections:**
- Timeout enforcement (default 30s)
- Process isolation (subprocess execution)
- No privilege escalation
- Exit code validation

**Best practices:**
- Review hook code before installation
- Use timeouts on all hooks
- Test in non-production first
- Use specific matchers (avoid `*` when possible)

## Documentation

- [Complete Specification](SPEC.md) - Architecture and design
- [Example Hooks](examples/hooks/) - Working examples
- [Security Guide](SPEC.md#security-considerations) - Detailed security info

## Contributing

Contributions welcome! Please ensure alignment with:
- Shell-first approach (not Python)
- Claude Code format compatibility
- Security-conscious design
- Amplifier's modular philosophy

## License

MIT License - See LICENSE file for details

## Roadmap

**Phase 1 (Current)**: Core command hooks with exit codes and JSON responses  
**Phase 2**: Prompt-based hooks (LLM evaluation), additional events  
**Phase 3**: Foundation integration, hook marketplace, CLI management
