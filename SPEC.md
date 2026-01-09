# Shell Hooks Module for Amplifier - Specification

**Version**: 1.0  
**Date**: 2026-01-06  
**Status**: Draft

## Executive Summary

This specification describes a bridge module that enables Amplifier to execute Claude Code-compatible hooks. Rather than integrating with Claude Code's configuration system, this bridge provides a standalone `.amplifier/hooks/` directory where users can install and share hooks compatible with Claude Code's format, particularly from Claude Code plugins.

## Motivation

Amplifier needs shell-based extensibility to complement Python hooks. Shell hooks provide:

1. **Simplicity**: No Python coding required, just shell scripts
2. **Portability**: Use any language or system command
3. **Reusability**: Share hooks as plugins across projects
4. **Ecosystem compatibility**: Leverage Claude Code's proven format and their plugin ecosystem

By adopting Claude Code's hook format, we get:
- Battle-tested JSON schema
- Compatible with existing Claude Code plugins
- Familiar patterns for users from that ecosystem
- Proven lifecycle event taxonomy

## Design Principles

1. **Standalone**: No dependency on `.claude/` folder or Claude Code installation
2. **Plugin-friendly**: Easy to install hooks from plugin repositories
3. **Composable**: Works alongside native Amplifier hooks
4. **Simple**: Minimal configuration, just drop hooks into `.amplifier/hooks/`
5. **Compatible**: Support Claude Code hook format and conventions

## Architecture

### Directory Structure

```
.amplifier/
├── hooks/
│   ├── hooks.json              # Hook registry configuration
│   ├── bash-validator/         # Example plugin
│   │   ├── hooks.json          # Plugin hook definitions
│   │   └── validate.sh         # Hook script
│   └── auto-formatter/         # Another plugin
│       ├── hooks.json
│       └── format.py
└── settings.json               # Standard Amplifier settings
```

### Hook Configuration Format

We adopt Claude Code's hook configuration format for compatibility:

```json
{
  "description": "Automatic code formatting",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${AMPLIFIER_HOOKS_DIR}/auto-formatter/format.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Component Architecture

```
┌─────────────────────────────────────────────┐
│         Amplifier Core Events                │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│    Claude Code Hook Bridge Module           │
│  ┌─────────────────────────────────────┐   │
│  │  Event Mapper                        │   │
│  │  (Amplifier → Claude Code events)    │   │
│  └─────────────┬───────────────────────┘   │
│                │                             │
│  ┌─────────────▼───────────────────────┐   │
│  │  Hook Registry                       │   │
│  │  (Load from .amplifier/hooks/)       │   │
│  └─────────────┬───────────────────────┘   │
│                │                             │
│  ┌─────────────▼───────────────────────┐   │
│  │  Matcher Engine                      │   │
│  │  (Regex matching on tool names)      │   │
│  └─────────────┬───────────────────────┘   │
│                │                             │
│  ┌─────────────▼───────────────────────┐   │
│  │  Command Executor                    │   │
│  │  (Subprocess with JSON stdin/stdout) │   │
│  └─────────────┬───────────────────────┘   │
│                │                             │
│  ┌─────────────▼───────────────────────┐   │
│  │  Response Translator                 │   │
│  │  (Exit codes/JSON → HookResult)      │   │
│  └─────────────────────────────────────┘   │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│         Amplifier Hook System                │
│         (HookResult processing)              │
└─────────────────────────────────────────────┘
```

## Event Mapping

### Supported Events (Phase 1)

| Claude Code Event | Amplifier Event | Priority | Notes |
|-------------------|-----------------|----------|-------|
| `PreToolUse` | `tool:pre` | High | Before tool execution, can block |
| `PostToolUse` | `tool:post` | High | After tool completion |
| `UserPromptSubmit` | `prompt:submit` | High | User prompt submission |
| `SessionStart` | `session:start` | Medium | Session initialization |
| `SessionEnd` | `session:end` | Medium | Session cleanup |

### Future Events (Phase 2)

| Claude Code Event | Amplifier Event | Notes |
|-------------------|-----------------|-------|
| `Stop` | `orchestrator:stop` | Needs new event type |
| `SubagentStop` | `task:post` | Task tool completion |
| `PermissionRequest` | `tool:ask_user` | When ask_user triggered |
| `PreCompact` | `context:pre_compact` | Needs new event type |
| `Notification` | Various | Map to specific notification types |

## Data Translation

### Input: Amplifier → Claude Code

Each Claude Code event expects specific JSON structure on stdin.

#### PreToolUse Format
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la",
    "description": "List files"
  },
  "timestamp": "2026-01-06T19:48:34Z"
}
```

#### PostToolUse Format
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la"
  },
  "tool_result": {
    "stdout": "...",
    "stderr": "",
    "returncode": 0
  },
  "timestamp": "2026-01-06T19:48:35Z"
}
```

#### UserPromptSubmit Format
```json
{
  "prompt": "Please implement the login feature",
  "timestamp": "2026-01-06T19:48:30Z"
}
```

#### SessionStart Format
```json
{
  "session_id": "f55bc601-9746-43b8-819f-279401de2434",
  "trigger": "startup",
  "timestamp": "2026-01-06T19:48:00Z"
}
```

### Output: Claude Code → Amplifier

#### Exit Code Method

Simple hooks use exit codes:
- **0**: Success, allow operation (→ `HookResult(action="continue")`)
- **2**: Block operation (→ `HookResult(action="deny")`)
- **Other**: Error, treated as continue with warning

#### JSON Output Method

Advanced hooks return JSON on stdout:

```json
{
  "decision": "approve | block",
  "reason": "Explanation for blocking",
  "systemMessage": "Message shown to user",
  "newContent": "Modified content (for modify action)",
  "contextInjection": "Feedback to inject",
  "continue": false
}
```

**Translation to HookResult**:

| Claude Code Response | HookResult Action | Fields |
|---------------------|-------------------|--------|
| `decision: "block"` | `deny` | `reason`, `user_message` |
| `newContent` present | `modify` | `data` with modified content |
| `contextInjection` present | `inject_context` | `context_injection`, `user_message` |
| `decision: "approve"` | `continue` | `user_message` if present |
| Exit code 2 | `deny` | `reason` from stderr |
| Exit code 0 | `continue` | - |

## Matcher System

Claude Code uses regex patterns to filter which tools trigger hooks:

- `"Bash"` - Exact match for Bash tool
- `"Edit|Write"` - Match Edit OR Write tools
- `"Notebook.*"` - Regex pattern for Notebook tools
- `"*"` or `""` - Match all tools

**Implementation**:
```python
def matches_pattern(tool_name: str, matcher: str) -> bool:
    """Check if tool name matches Claude Code matcher pattern."""
    if not matcher or matcher == "*":
        return True
    try:
        return bool(re.fullmatch(matcher, tool_name))
    except re.error:
        # Fallback to exact match if regex is invalid
        return tool_name == matcher
```

## Environment Variables

Hook commands have access to these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `AMPLIFIER_PROJECT_DIR` | Project root directory | `/home/user/myproject` |
| `AMPLIFIER_HOOKS_DIR` | Hooks directory | `/home/user/myproject/.amplifier/hooks` |
| `AMPLIFIER_SESSION_ID` | Current session ID | `f55bc601-9746-43b8-819f-279401de2434` |
| `AMPLIFIER_ENV_FILE` | (SessionStart only) Env persistence file | `/tmp/amplifier-env-xyz` |

For compatibility, we also provide Claude Code equivalents:
- `CLAUDE_PROJECT_DIR` → Same as `AMPLIFIER_PROJECT_DIR`
- `CLAUDE_ENV_FILE` → Same as `AMPLIFIER_ENV_FILE`

## Hook Installation

### Manual Installation

```bash
# Create hooks directory
mkdir -p .amplifier/hooks/my-hook

# Copy hook files
cp hook.sh .amplifier/hooks/my-hook/
cp hooks.json .amplifier/hooks/my-hook/

# Make script executable
chmod +x .amplifier/hooks/my-hook/hook.sh
```

### From Claude Code Plugin

Claude Code plugins often have this structure:
```
claude-code-plugin-formatter/
├── hooks/
│   ├── hooks.json
│   └── format.sh
└── README.md
```

To install:
```bash
# Clone plugin
git clone https://github.com/user/claude-code-plugin-formatter

# Copy hooks to Amplifier
cp -r claude-code-plugin-formatter/hooks .amplifier/hooks/formatter

# Update paths in hooks.json if needed
sed -i 's/${CLAUDE_PLUGIN_ROOT}/${AMPLIFIER_HOOKS_DIR}\/formatter/g' \
  .amplifier/hooks/formatter/hooks.json
```

### Future: Amplifier CLI Support

```bash
# Phase 2: CLI installation
amplifier hooks install https://github.com/user/claude-code-plugin-formatter
amplifier hooks list
amplifier hooks enable formatter
amplifier hooks disable formatter
```

## Security Considerations

### Hook Execution Risks

Hooks run as **shell commands with user permissions**. Malicious hooks can:
- Exfiltrate data
- Modify files
- Execute arbitrary code
- Access secrets

### Security Best Practices

1. **Review before installing**: Always review hook code before installation
2. **Trusted sources only**: Only install hooks from trusted sources
3. **Least privilege**: Hooks run with user's permissions (can't elevate)
4. **Timeout enforcement**: All hooks have configurable timeouts (default 30s)
5. **Sandbox consideration**: Future phase may add sandboxing (Docker, bubblewrap)

### User Controls

```yaml
# In bundle configuration
hooks:
  - module: hooks-claude-code-bridge
    config:
      enabled: true
      allow_user_hooks: true       # Allow .amplifier/hooks/
      allow_project_hooks: true    # Allow project-specific hooks
      default_timeout: 30          # Default timeout in seconds
      max_timeout: 300             # Maximum allowed timeout
```

## Configuration Discovery

### Load Order (Priority)

1. `.amplifier/hooks/hooks.json` - Root registry
2. `.amplifier/hooks/*/hooks.json` - Individual plugin configs

All configs are merged, with matchers and hooks combined for each event.

### Configuration Merging

```python
def merge_hook_configs(configs: list[dict]) -> dict:
    """Merge multiple hook configurations."""
    merged = {"hooks": {}}
    
    for config in configs:
        for event_name, matchers in config.get("hooks", {}).items():
            if event_name not in merged["hooks"]:
                merged["hooks"][event_name] = []
            merged["hooks"][event_name].extend(matchers)
    
    return merged
```

## Implementation Phases

### Phase 1: MVP (Initial Implementation)

**Scope**:
- Core bridge module with event mapping
- Support command hooks (not prompt-based)
- Basic events: PreToolUse, PostToolUse, UserPromptSubmit, SessionStart, SessionEnd
- Exit code and JSON response parsing
- Manual hook installation to `.amplifier/hooks/`

**Deliverables**:
- `amplifier-module-hooks-claude-code` module
- Configuration loader
- Command executor
- Response translator
- Basic example hooks
- Documentation

**Acceptance Criteria**:
- Can load hooks from `.amplifier/hooks/`
- Can execute bash command hooks
- Can parse exit codes and JSON responses
- Can translate to HookResult correctly
- Example hooks work end-to-end

### Phase 2: Enhanced Support

**Scope**:
- Prompt-based hooks (LLM evaluation)
- Additional events: Stop, SubagentStop, PreCompact, Notification
- Environment variable persistence (AMPLIFIER_ENV_FILE)
- Hook enable/disable controls
- Better error handling and logging

**Deliverables**:
- Prompt-based hook executor
- Extended event mappings
- Environment file support
- Control configuration
- Enhanced documentation

### Phase 3: Ecosystem Integration

**Scope**:
- CLI commands for hook management
- Hook marketplace/catalog
- Plugin package format
- Migration tools (Claude Code → Amplifier)
- Performance optimizations

**Deliverables**:
- `amplifier hooks` CLI commands
- Plugin package specification
- Hook discovery service
- Migration scripts
- Performance benchmarks

## Example Use Cases

### Use Case 1: Bash Command Logging

**Hook**: Log all bash commands to a file

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
            "command": "jq -r '.tool_input.command' >> ${AMPLIFIER_PROJECT_DIR}/bash-commands.log"
          }
        ]
      }
    ]
  }
}
```

### Use Case 2: Automatic Code Formatting

**Hook**: Format TypeScript files after editing

```json
{
  "description": "Auto-format TypeScript",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${AMPLIFIER_HOOKS_DIR}/formatter/format-ts.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Script `format-ts.sh`:
```bash
#!/bin/bash
file_path=$(jq -r '.tool_input.file_path')
if [[ "$file_path" == *.ts ]]; then
    npx prettier --write "$file_path"
    echo "✓ Formatted $file_path"
fi
```

### Use Case 3: Production File Protection

**Hook**: Block writes to production config files

```json
{
  "description": "Protect production files",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${AMPLIFIER_HOOKS_DIR}/protection/check-file.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Script `check-file.py`:
```python
#!/usr/bin/env python3
import json
import sys

data = json.load(sys.stdin)
file_path = data.get('tool_input', {}).get('file_path', '')

# Block writes to production files
protected = ['.env.production', 'package-lock.json', '.git/']
if any(p in file_path for p in protected):
    print(json.dumps({
        "decision": "block",
        "reason": f"Cannot modify protected file: {file_path}",
        "systemMessage": "⛔ Protected file - manual approval required"
    }))
    sys.exit(2)

sys.exit(0)
```

### Use Case 4: Lint Feedback Injection

**Hook**: Run linter and inject feedback to agent

```json
{
  "description": "Python linting feedback",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${AMPLIFIER_HOOKS_DIR}/linter/pylint-feedback.py",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Script `pylint-feedback.py`:
```python
#!/usr/bin/env python3
import json
import sys
import subprocess

data = json.load(sys.stdin)
file_path = data.get('tool_input', {}).get('file_path', '')

if not file_path.endswith('.py'):
    sys.exit(0)

# Run pylint
result = subprocess.run(
    ['pylint', file_path],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    # Inject linting errors as context
    print(json.dumps({
        "decision": "approve",
        "contextInjection": f"Linting errors in {file_path}:\n{result.stdout}",
        "systemMessage": "⚠️ Linting issues detected"
    }))
else:
    print(json.dumps({
        "decision": "approve",
        "systemMessage": "✓ Lint check passed"
    }))
```

## Testing Strategy

### Unit Tests
- Configuration loading and merging
- Event mapping (Amplifier → Claude Code)
- Matcher regex evaluation
- Response translation (exit codes, JSON)
- Environment variable injection

### Integration Tests
- End-to-end hook execution
- Multiple hooks on same event
- Hook timeout handling
- Error propagation
- HookResult generation

### Example Hook Tests
- Bash command logger
- File format validator
- Production file protector
- Context injection hook

## Performance Considerations

### Subprocess Overhead

Each hook spawns a subprocess. For performance:
- **Cache hook discovery**: Load configs once at startup
- **Parallel execution**: Run multiple hooks concurrently
- **Timeout aggressively**: Default 30s, but allow shorter
- **Skip on pattern mismatch**: Don't spawn if matcher doesn't match

### Optimization Strategies

```python
# Pre-compile regex matchers
class OptimizedMatcher:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.regex = re.compile(pattern) if pattern and pattern != "*" else None
    
    def matches(self, tool_name: str) -> bool:
        if self.regex is None:
            return True
        return bool(self.regex.fullmatch(tool_name))

# Batch hook execution
async def execute_hooks_parallel(hooks: list, data: dict):
    tasks = [execute_hook(hook, data) for hook in hooks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return combine_results(results)
```

## Open Questions

1. **Sandboxing**: Should Phase 2 include Docker/bubblewrap sandboxing for untrusted hooks?
2. **Hook marketplace**: Is there interest in a central registry for sharing hooks?
3. **Prompt hooks**: Should we use same provider as main agent or dedicated fast model?
4. **Versioning**: How to handle hook API version compatibility?
5. **Migration**: Should we provide tools to convert existing Claude Code setups?

## Success Metrics

- Number of hooks installed from Claude Code plugins
- Performance overhead (median latency per hook)
- User adoption rate
- Security incidents (target: 0)
- Community-contributed hooks

## References

### Claude Code Documentation
- [Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)

### Amplifier Documentation
- `core:docs/HOOKS_API.md` - Hook system API
- `foundation:examples/18_custom_hooks.py` - Custom hook examples

### Related Work
- Claude Code plugin ecosystem
- Amplifier module system
- Git hooks for inspiration

---

## Appendix A: Complete Example Plugin

**Directory**: `.amplifier/hooks/bash-validator/`

**File**: `hooks.json`
```json
{
  "description": "Validate bash commands before execution",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${AMPLIFIER_HOOKS_DIR}/bash-validator/validate.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**File**: `validate.sh`
```bash
#!/bin/bash
# Read JSON from stdin
input=$(cat)

# Extract command
command=$(echo "$input" | jq -r '.tool_input.command')

# Block dangerous commands
dangerous=("rm -rf /" "dd if=" "mkfs" ":(){ :|:& };:")

for pattern in "${dangerous[@]}"; do
    if [[ "$command" == *"$pattern"* ]]; then
        echo "{\"decision\": \"block\", \"reason\": \"Dangerous command blocked: $pattern\", \"systemMessage\": \"⛔ Security: Blocked dangerous operation\"}" 
        exit 2
    fi
done

# Allow command
exit 0
```

**File**: `README.md`
```markdown
# Bash Command Validator

Blocks dangerous bash commands before execution.

## Installation

\`\`\`bash
cp -r bash-validator .amplifier/hooks/
chmod +x .amplifier/hooks/bash-validator/validate.sh
\`\`\`

## Blocked Patterns

- `rm -rf /`
- `dd if=`
- `mkfs`
- Fork bombs

## Customization

Edit `validate.sh` to add more patterns to the `dangerous` array.
\`\`\`
```

## Appendix B: Hook Registry Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "description": {
      "type": "string",
      "description": "Human-readable description of the hook"
    },
    "hooks": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "matcher": {
              "type": "string",
              "description": "Regex pattern to match tool names"
            },
            "hooks": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "type": {
                    "type": "string",
                    "enum": ["command", "prompt"],
                    "description": "Hook execution type"
                  },
                  "command": {
                    "type": "string",
                    "description": "Shell command to execute (required if type=command)"
                  },
                  "prompt": {
                    "type": "string",
                    "description": "LLM prompt for evaluation (required if type=prompt)"
                  },
                  "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds",
                    "default": 30
                  }
                },
                "required": ["type"]
              }
            }
          },
          "required": ["hooks"]
        }
      }
    }
  },
  "required": ["hooks"]
}
```
