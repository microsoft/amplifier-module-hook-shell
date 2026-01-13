# Shell Hooks Module for Amplifier - Specification

**Version**: 1.1  
**Date**: 2026-01-10  
**Status**: Phase 1 Complete, Phase 2 Ready

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
┌─────────────────────────────────────────────────┐
│         Amplifier Core Events                   │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│    Shell Hook Bridge Module                     │
│  ┌─────────────────────────────────────────┐   │
│  │  Event Mapper                           │   │
│  │  (Amplifier → Claude Code events)       │   │
│  └─────────────┬───────────────────────────┘   │
│                │                               │
│  ┌─────────────▼───────────────────────────┐   │
│  │  Hook Registry                          │   │
│  │  (Load from .amplifier/hooks/)          │   │
│  └─────────────┬───────────────────────────┘   │
│                │                               │
│  ┌─────────────▼───────────────────────────┐   │
│  │  Matcher Engine                         │   │
│  │  (Regex matching on tool names)         │   │
│  └─────────────┬───────────────────────────┘   │
│                │                               │
│  ┌─────────────▼───────────────────────────┐   │
│  │  Command Executor                       │   │
│  │  (Subprocess with JSON stdin/stdout)    │   │
│  └─────────────┬───────────────────────────┘   │
│                │                               │
│  ┌─────────────▼───────────────────────────┐   │
│  │  Response Translator                    │   │
│  │  (Exit codes/JSON → HookResult)         │   │
│  └─────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│         Amplifier Hook System                   │
│         (HookResult processing)                 │
└─────────────────────────────────────────────────┘
```

## Event Mapping

### Complete Event Mapping

All Claude Code events map to **existing** Amplifier core events. No core changes required.

| Claude Code Event | Amplifier Event | Status | Matchers | Notes |
|-------------------|-----------------|--------|----------|-------|
| `PreToolUse` | `tool:pre` | ✅ Phase 1 | Tool name regex | Before tool execution, can block |
| `PostToolUse` | `tool:post` | ✅ Phase 1 | Tool name regex | After tool completion |
| `UserPromptSubmit` | `prompt:submit` | ✅ Phase 1 | - | User prompt submission |
| `SessionStart` | `session:start` | ✅ Phase 1 | startup, resume, clear, compact | Session initialization |
| `SessionEnd` | `session:end` | ✅ Phase 1 | - | Session cleanup |
| `Stop` | `orchestrator:complete` | 🔲 Phase 2 | - | Main agent finished responding |
| `SubagentStop` | `tool:post` | 🔲 Phase 2 | `Task` | Task tool completion (subagent) |
| `PreCompact` | `context:pre_compact` | 🔲 Phase 2 | manual, auto | Before context compaction |
| `PermissionRequest` | `approval:required` | 🔲 Phase 2 | Tool name regex | When permission dialog shown |
| `Notification` | `user:notification` | 🔲 Phase 2 | permission_prompt, idle_prompt, auth_success | Various notifications |

### SessionStart Matchers

SessionStart supports matchers to differentiate trigger types:

| Matcher | Amplifier Event | Description |
|---------|-----------------|-------------|
| `startup` | `session:start` | New session startup |
| `resume` | `session:resume` | Resuming existing session |
| `clear` | `session:start` (with clear flag) | After /clear command |
| `compact` | `context:post_compact` | After context compaction |

### SubagentStop Pattern

SubagentStop is handled as a special case of `tool:post` by matching the tool name:

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [{"type": "command", "command": "./check-subagent.sh"}]
      }
    ]
  }
}
```

Internally mapped to:
```python
# SubagentStop → tool:post with matcher "Task"
if event == "SubagentStop":
    amplifier_event = "tool:post"
    implicit_matcher = "Task"
```

## Data Translation

### Input: Amplifier → Claude Code

Each Claude Code event expects specific JSON structure on stdin.

#### PreToolUse Input
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

#### PostToolUse Input
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

#### UserPromptSubmit Input
```json
{
  "prompt": "Please implement the login feature",
  "timestamp": "2026-01-06T19:48:30Z"
}
```

#### SessionStart Input
```json
{
  "session_id": "f55bc601-9746-43b8-819f-279401de2434",
  "trigger": "startup",
  "timestamp": "2026-01-06T19:48:00Z"
}
```

#### Stop/SubagentStop Input (Phase 2)
```json
{
  "stop_hook_active": true,
  "timestamp": "2026-01-06T19:49:00Z"
}
```

#### PreCompact Input (Phase 2)
```json
{
  "trigger": "auto",
  "timestamp": "2026-01-06T19:50:00Z"
}
```

#### Notification Input (Phase 2)
```json
{
  "type": "permission_prompt",
  "message": "Allow write to file.txt?",
  "timestamp": "2026-01-06T19:51:00Z"
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

### Event-Specific Decision Control

Different events support different decision controls:

| Event | Supports Block | Supports Modify | Supports Context Injection |
|-------|---------------|-----------------|---------------------------|
| PreToolUse | ✅ | ✅ | ✅ |
| PostToolUse | ❌ | ❌ | ✅ |
| UserPromptSubmit | ✅ | ✅ | ✅ |
| Stop/SubagentStop | ✅ (prevent stop) | ❌ | ❌ |
| PermissionRequest | ✅ (auto-deny/allow) | ❌ | ❌ |
| SessionStart | ❌ | ❌ | ✅ |
| SessionEnd | ❌ | ❌ | ❌ |

## Matcher System

Claude Code uses regex patterns to filter which tools trigger hooks:

- `"Bash"` - Exact match for Bash tool
- `"Edit|Write"` - Match Edit OR Write tools
- `"Notebook.*"` - Regex pattern for Notebook tools
- `"*"` or `""` - Match all tools
- Case-insensitive by default

**MCP Tool Naming** (Phase 2):
MCP tools use the pattern `mcp__<server>__<toolName>`. Configure matchers like:
```json
{"matcher": "mcp__filesystem__.*"}
```

**Implementation**:
```python
def matches_pattern(tool_name: str, matcher: str) -> bool:
    """Check if tool name matches Claude Code matcher pattern."""
    if not matcher or matcher == "*":
        return True
    try:
        return bool(re.fullmatch(matcher, tool_name, re.IGNORECASE))
    except re.error:
        # Fallback to exact match if regex is invalid
        return tool_name.lower() == matcher.lower()
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

### Environment Variable Persistence (Phase 2)

SessionStart hooks can persist environment variables for the session:

```bash
#!/bin/bash
# Write to AMPLIFIER_ENV_FILE to persist vars
echo "export PROJECT_VERSION=1.2.3" >> "$AMPLIFIER_ENV_FILE"
echo "export BUILD_ID=$(date +%s)" >> "$AMPLIFIER_ENV_FILE"
```

## Hooks in Skills (Phase 1.5)

Claude Code supports hooks embedded in Skills, Agents, and Slash Commands via frontmatter. This is a **key integration point** for Amplifier.

### Skill Frontmatter Format

```yaml
---
name: secure-operations
description: Perform operations with security checks
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/security-check.sh"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
---
```

### Lifecycle Scoping

Component-scoped hooks:
- Only run when the component (skill/agent) is active
- Automatically cleaned up when component finishes
- Support `once: true` to run only once per session

### Integration with Amplifier Skills

Requires coordination with `amplifier-module-tool-skills`:
1. Skills loader parses `hooks:` section from frontmatter
2. Passes hook configs to hook-shell bridge
3. Bridge registers handlers with lifecycle scope
4. Cleanup on skill completion

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

### Future: Amplifier CLI Support (Phase 3)

```bash
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
  - module: hook-shell
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

### Phase 1: MVP ✅ COMPLETE

**Scope**:
- Core bridge module with event mapping
- Support command hooks (not prompt-based)
- Basic events: PreToolUse, PostToolUse, UserPromptSubmit, SessionStart, SessionEnd
- Exit code and JSON response parsing
- Manual hook installation to `.amplifier/hooks/`

**Deliverables**:
- `amplifier-module-hook-shell` module ✅
- Configuration loader ✅
- Command executor ✅
- Response translator ✅
- Basic example hooks ✅
- Documentation ✅
- Unit tests (86% coverage) ✅
- Integration tests ✅

**Acceptance Criteria** (all met):
- ✅ Can load hooks from `.amplifier/hooks/`
- ✅ Can execute bash command hooks
- ✅ Can parse exit codes and JSON responses
- ✅ Can translate to HookResult correctly
- ✅ Example hooks work end-to-end

### Phase 1.5: Skills Integration ✅ COMPLETE

**Scope**:
- Hooks embedded in skill frontmatter
- Lifecycle-scoped hooks (active when skill loaded, cleanup on unload)
- Coordination with `tool-skills` module via events

**Deliverables**:
- ✅ `hooks` field in SkillMetadata dataclass (tool-skills module)
- ✅ Frontmatter hook parser in discovery.py
- ✅ `skill:loaded` event includes hooks config and skill_directory
- ✅ `skill:unloaded` event for cleanup
- ✅ Event listeners in hook-shell for skill events
- ✅ Scoped hook registration/cleanup in bridge.py
- ✅ Relative path resolution for skill hook commands
- ✅ Example skill with hooks (`examples/skill-with-hooks/`)
- ✅ E2E tests validated in shadow environment

**Acceptance Criteria** (all met):
- ✅ Skills with `hooks:` frontmatter are discovered correctly
- ✅ Loading a skill registers its hooks dynamically
- ✅ Skill hooks execute alongside directory-based hooks
- ✅ Hooks are cleaned up when skill is unloaded (session end)
- ✅ Relative paths in hook commands resolve to skill directory

**Why Priority**: This is the key differentiator - portable skills with built-in hooks.

### Phase 2: Extended Events ✅ COMPLETE

**Scope** (no core changes needed - all events exist):
- ✅ Stop event (`prompt:complete`)
- ✅ SubagentStop (`tool:post` with Task tool matcher)
- ✅ PreCompact (`context:pre_compact`)
- ✅ PermissionRequest (`approval:required`)
- ✅ Notification (`user:notification`)
- ✅ SessionStart matchers (startup/resume/clear/compact)
- ✅ Environment variable persistence (`AMPLIFIER_ENV_FILE`)
- ⏳ Prompt-based hooks (`type: "prompt"`) - moved to Phase 2.5

**Deliverables**:
- ✅ Extended event mappings in bridge.py
- ✅ Event handlers for all Phase 2 events
- ✅ SessionStart trigger-based matching
- ✅ Environment file persistence in executor.py
- ✅ AMPLIFIER_ENV_FILE and CLAUDE_ENV_FILE support
- ✅ Comprehensive tests (66 tests, 78% coverage)

### Phase 2.5: Prompt-Based Hooks ✅ COMPLETE

**Scope**:
- ✅ `type: "prompt"` hook execution
- ⏳ Fast model (Haiku-class) for evaluation - **FUTURE** (see note below)
- ✅ `$ARGUMENTS` placeholder expansion
- ✅ Response schema: `{ok: true/false, reason: "..."}`

**Deliverables**:
- ✅ `_execute_prompt_hook()` method in bridge.py
- ✅ `_expand_arguments()` for $ARGUMENTS placeholder
- ✅ `_parse_prompt_response()` for flexible response parsing
- ✅ Integration with `_execute_hooks()` for type="prompt" hooks
- ✅ Coordinator passed to ShellHookBridge for provider access
- ✅ Comprehensive tests for prompt hooks

**Best for**:
- Stop hooks (intelligent completion detection)
- SubagentStop (task completion evaluation)
- Complex permission decisions

**Note**: Currently uses session's registered provider. Future enhancement: model override
for fast/cheap model (e.g., Haiku) - pending provider tier support in amplifier-core.

**Example configuration**:
```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Has the user's original request been fully addressed? The task was: $ARGUMENTS. Answer with JSON: {\"ok\": true/false, \"reason\": \"...\"}"
          }
        ]
      }
    ]
  }
}
```

### Phase 3: Ecosystem Integration (Partial)

**Completed**:
- ✅ Parallel hook execution (`parallel: true` in matcher groups)
- ✅ `_execute_single_hook()` method for reusable hook execution
- ✅ `asyncio.gather()` for concurrent hook execution
- ✅ Short-circuit on first blocking result in parallel mode
- ✅ Backward compatible (sequential by default)

**Parallel Execution Configuration**:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "parallel": true,
        "hooks": [
          {"type": "command", "command": "./check1.sh"},
          {"type": "command", "command": "./check2.sh"},
          {"type": "command", "command": "./check3.sh"}
        ]
      }
    ]
  }
}
```

**Deferred to Post-Upstream**:
The following Phase 3 items are deferred until after upstream integration:
- CLI commands (`amplifier hooks install/list/enable/disable`)
- Migration tools (Claude Code → Amplifier conversion)
- Plugin package format and specification
- Hook discovery service / marketplace

## Testing Strategy

### Unit Tests ✅
- Configuration loading and merging
- Event mapping (Amplifier → Claude Code)
- Matcher regex evaluation
- Response translation (exit codes, JSON)
- Environment variable injection

### Integration Tests ✅
- End-to-end hook execution
- Blocking hooks (exit code 2)
- JSON block responses
- Context injection
- Module mount with HookRegistry
- Regex pattern matching
- Session lifecycle events

### Example Hook Tests
- Bash command logger
- File format validator
- Production file protector
- Context injection hook

## Performance Considerations

### Subprocess Overhead

Each hook spawns a subprocess. For performance:
- **Cache hook discovery**: Load configs once at startup ✅
- **Parallel execution**: Run multiple hooks concurrently ✅ (Phase 3)
- **Timeout aggressively**: Default 30s, but allow shorter ✅
- **Skip on pattern mismatch**: Don't spawn if matcher doesn't match ✅

### Optimization Strategies

```python
# Pre-compile regex matchers (implemented)
class OptimizedMatcher:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.regex = re.compile(pattern, re.IGNORECASE) if pattern and pattern != "*" else None
    
    def matches(self, tool_name: str) -> bool:
        if self.regex is None:
            return True
        return bool(self.regex.fullmatch(tool_name))

# Parallel hook execution (implemented in Phase 3)
# Configure with "parallel": true in matcher group
async def _execute_hooks(self, ...):
    for matcher_group in matching_groups:
        hooks = matcher_group.get("hooks", [])
        parallel = matcher_group.get("parallel", False)
        
        if parallel:
            results = await asyncio.gather(
                *[self._execute_single_hook(h, ...) for h in hooks],
                return_exceptions=True
            )
            # Check for any blocking result
            for result in results:
                if result.get("action") != "continue":
                    return result
        else:
            # Sequential (default)
            for hook in hooks:
                result = await self._execute_single_hook(hook, ...)
                if result.get("action") != "continue":
                    return result
```

## Open Questions

1. ~~**Core events**: Do we need new events in amplifier-core?~~ **RESOLVED: No, all events exist**
2. **Sandboxing**: Should Phase 3 include Docker/bubblewrap sandboxing for untrusted hooks?
3. **Hook marketplace**: Is there interest in a central registry for sharing hooks?
4. **Prompt hooks model**: Should we use same provider as main agent or dedicated fast model?
5. **Migration**: Should we provide tools to convert existing Claude Code setups?

## Success Metrics

- Number of hooks installed from Claude Code plugins
- Performance overhead (median latency per hook)
- User adoption rate
- Security incidents (target: 0)
- Community-contributed hooks

## References

### Claude Code Documentation
- [Hooks Guide](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [Hooks Reference](https://docs.anthropic.com/en/docs/claude-code/hooks)

### Amplifier Documentation
- `core:docs/HOOKS_API.md` - Hook system API
- `foundation:examples/18_custom_hooks.py` - Custom hook examples

### Related Work
- Claude Code plugin ecosystem
- Amplifier module system
- Git hooks for inspiration

---

## Appendix A: Complete Event Mapping Reference

```python
# Complete mapping from Claude Code events to Amplifier events
CLAUDE_TO_AMPLIFIER_EVENTS = {
    # Phase 1 (implemented)
    "PreToolUse": "tool:pre",
    "PostToolUse": "tool:post",
    "UserPromptSubmit": "prompt:submit",
    "SessionStart": "session:start",
    "SessionEnd": "session:end",
    
    # Phase 2 (all events exist in amplifier-core)
    "Stop": "orchestrator:complete",
    "SubagentStop": "tool:post",  # with implicit matcher "Task"
    "PreCompact": "context:pre_compact",
    "PermissionRequest": "approval:required",
    "Notification": "user:notification",
}

# SessionStart matchers map to different events
SESSION_START_MATCHERS = {
    "startup": "session:start",
    "resume": "session:resume",
    "clear": "session:start",  # with clear flag in data
    "compact": "context:post_compact",
}
```

## Appendix B: Complete Example Plugin

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

## Appendix C: Hook Registry Schema

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
                  },
                  "once": {
                    "type": "boolean",
                    "description": "Run only once per session (skills only)",
                    "default": false
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
