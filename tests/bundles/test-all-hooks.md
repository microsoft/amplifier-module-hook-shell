---
bundle:
  name: test-all-hooks
  version: 0.1.0
  description: Comprehensive test bundle with all hook types

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

hooks:
  - module: hook-shell
    source: git+https://github.com/robotdad/amplifier-module-hook-shell@main
    config:
      hooks_dirs:
        - .amplifier/hooks
---

# Test Bundle: All Hooks

Comprehensive test bundle that includes all hook types for full testing.

## Setup

Copy all test hooks:

```bash
# Formatters
cp -r tests/hooks/python-formatter .amplifier/hooks/
cp -r tests/hooks/js-formatter .amplifier/hooks/

# Linters
cp -r tests/hooks/python-linter .amplifier/hooks/
cp -r tests/hooks/js-linter .amplifier/hooks/

# Security
cp -r tests/hooks/file-guard .amplifier/hooks/
cp -r examples/hooks/bash-validator .amplifier/hooks/

# Logging
cp -r tests/hooks/command-logger .amplifier/hooks/
```

## Hook Summary

| Hook | Event | Matcher | Action |
|------|-------|---------|--------|
| python-formatter | PostToolUse | Edit\|Write | Format .py files |
| js-formatter | PostToolUse | Edit\|Write | Format .js/.ts files |
| python-linter | PostToolUse | Edit\|Write | Lint .py, inject context |
| js-linter | PostToolUse | Edit\|Write | Lint .js/.ts, inject context |
| file-guard | PreToolUse | Edit\|Write | Block protected paths |
| bash-validator | PreToolUse | Bash | Block dangerous commands |
| command-logger | Pre+PostToolUse | Bash | Audit log |

## Test Matrix

| Test | Expected |
|------|----------|
| Write badly formatted Python | Auto-formatted |
| Write Python with lint errors | Context injected with errors |
| Write to .env | BLOCKED |
| Run rm -rf / | BLOCKED |
| Run echo hello | Allowed + logged |
