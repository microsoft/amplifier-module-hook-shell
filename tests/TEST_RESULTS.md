# Shell Hooks Test Results

**Date**: 2026-01-09  
**Environment**: Shadow environment with local source override  
**Status**: ✅ All tests passed

## Test Summary

| Hook | Type | Trigger | Status |
|------|------|---------|--------|
| python-formatter | PostToolUse | Edit\|Write on `.py` | ✅ Pass |
| python-linter | PostToolUse | Edit\|Write on `.py` | ✅ Pass |
| js-formatter | PostToolUse | Edit\|Write on `.js/.ts` | ✅ Pass |
| js-linter | PostToolUse | Edit\|Write on `.js/.ts` | ✅ Pass |
| file-guard | PreToolUse (Blocking) | Edit\|Write | ✅ Pass |
| bash-validator | PreToolUse (Blocking) | Bash | ✅ Pass |
| command-logger | Pre+PostToolUse | Bash | ✅ Pass |

---

## Detailed Results

### Test A: Python Formatter Hook

| Aspect | Result |
|--------|--------|
| **Input** | `def foo( x,y ):return x+y` |
| **Output** | Properly formatted Python |
| **Hook Response** | `{"decision": "approve", "reason": "Formatted Python file with ruff"}` |

**Before:**
```python
def foo( x,y ):return x+y
```

**After:**
```python
def foo(x, y):
    return x + y
```

### Test B: Python Linter Hook

| Aspect | Result |
|--------|--------|
| **Input** | `import os\nprint("hello")` |
| **Detection** | ✅ Unused import detected |
| **Context Injection** | ✅ Linting errors injected into agent context |

**Linting Output:**
```
F401 [*] `os` imported but unused
```

### Test C: File Guard Hook (BLOCKING)

| Test | Path | Expected | Actual | Exit Code |
|------|------|----------|--------|-----------|
| C1 | `.env` | BLOCKED | ✅ BLOCKED | 2 |
| C2 | `secrets.yaml` | BLOCKED | ✅ BLOCKED | 2 |
| C3 | `normal.txt` | ALLOWED | ✅ ALLOWED | 0 |

**Block Response:**
```json
{
  "decision": "block",
  "reason": "File path matches protected pattern: \\.env$",
  "systemMessage": "Blocked: Cannot write to protected file '.env'. This path is protected by file-guard hook."
}
```

### Test D: Bash Validator Hook (BLOCKING)

| Test | Command | Expected | Actual |
|------|---------|----------|--------|
| D1 | `rm -rf /` | BLOCKED | ✅ BLOCKED |
| D2 | `echo hello` | ALLOWED | ✅ ALLOWED |

### Test E: Command Logger Hook

| Aspect | Result |
|--------|--------|
| **Pre-execute logging** | ✅ Working |
| **Post-execute logging** | ✅ Working |
| **Log file** | `.amplifier/command-log.jsonl` |

**Log Entry Example:**
```json
{"timestamp": "2026-01-09T23:40:23Z", "event": "pre_execute", "command": "ls -la"}
{"timestamp": "2026-01-09T23:40:28Z", "event": "post_execute", "command": "ls -la", "result_preview": "..."}
```

---

## Test Configuration

### Bundle-based (MD with YAML frontmatter)

Test bundles in `tests/bundles/`:
- `test-formatters.md` - Python and JS formatter hooks
- `test-linters.md` - Python and JS linter hooks  
- `test-security.md` - file-guard and bash-validator
- `test-logging.md` - command-logger hook
- `test-all-hooks.md` - All hooks combined

### Settings-based (YAML)

Test settings in `tests/settings/`:
- `test-settings.yaml` - Full configuration with all options
- `test-settings-minimal.yaml` - Minimal configuration
- `test-settings-security-only.yaml` - Security-focused (PreToolUse only)

---

## How to Run Tests

### Manual Testing

1. Copy hooks to workspace:
```bash
mkdir -p .amplifier/hooks
cp -r tests/hooks/* .amplifier/hooks/
cp -r examples/hooks/bash-validator .amplifier/hooks/
```

2. Register a test bundle:
```bash
amplifier bundle add tests/bundles/test-all-hooks.md
```

3. Run Amplifier and test:
```bash
amplifier run "Create a Python file with bad formatting"
amplifier run "Try to write to .env"
amplifier run "Run rm -rf /"
```

### Automated Testing (pytest)

Unit tests in `tests/`:
- `test_loader.py` - Hook discovery and loading
- `test_matcher.py` - Regex pattern matching
- `test_translator.py` - Data format translation

```bash
uv run pytest tests/
```

---

## Notes

- **Amplifier built-in safety**: Dangerous commands like `rm -rf /` are blocked at the platform level as well. Shell hooks provide additional customizable protection.
- **Exit codes**: Exit code 2 = block operation; Exit code 0 = allow operation
- **Context injection**: Linter hooks can inject feedback into agent context so the agent can fix issues in the same turn.
