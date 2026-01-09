---
bundle:
  name: test-logging
  version: 0.1.0
  description: Test bundle for command logging hook

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

hooks:
  - module: hooks-shell
    source: git+https://github.com/robotdad/amplifier-module-hooks-shell@main
    config:
      hooks_dirs:
        - .amplifier/hooks
---

# Test Bundle: Command Logging

This bundle tests the command-logger hook that audits all bash commands.

## Hooks Included

Copy the logging hook to your project:

```bash
cp -r tests/hooks/command-logger .amplifier/hooks/
```

## Expected Behavior

- **PreToolUse on Bash**: Logs command with timestamp before execution
- **PostToolUse on Bash**: Logs result preview after execution
- Logs written to `.amplifier/command-log.jsonl`

## Log Format

```jsonl
{"timestamp": "2026-01-09T20:30:00Z", "event": "pre_execute", "command": "ls -la"}
{"timestamp": "2026-01-09T20:30:01Z", "event": "post_execute", "command": "ls -la", "result_preview": "..."}
```

## Test Cases

1. Run several bash commands
2. Verify `.amplifier/command-log.jsonl` contains entries
3. Check both pre and post events are logged
