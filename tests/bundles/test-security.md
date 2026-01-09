---
bundle:
  name: test-security
  version: 0.1.0
  description: Test bundle for security hooks (file-guard, bash-validator)

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

hooks:
  - module: hooks-shell
    source: git+https://github.com/robotdad/amplifier-module-hooks-shell@main
    config:
      hooks_dirs:
        - .amplifier/hooks
---

# Test Bundle: Security Hooks

This bundle tests security-focused hooks that block dangerous operations.

## Hooks Included

Copy security hooks to your project:

```bash
cp -r tests/hooks/file-guard .amplifier/hooks/
cp -r examples/hooks/bash-validator .amplifier/hooks/
```

## Expected Behavior

### file-guard (PreToolUse on Edit/Write)
- Blocks writes to protected paths: `/etc/`, `/usr/`, `.env`, `*.key`, `*.pem`, etc.
- Returns exit code 2 (block) with explanation

### bash-validator (PreToolUse on Bash)
- Blocks dangerous commands: `rm -rf /`, `chmod 777`, `curl | sh`, etc.
- Returns exit code 2 (block) with explanation

## Test Cases

1. Try to write to `.env` file - should be BLOCKED
2. Try to write to `secrets.yaml` - should be BLOCKED
3. Try to run `rm -rf /` - should be BLOCKED
4. Try to run `chmod 777 /` - should be BLOCKED
5. Write to normal file - should be ALLOWED
6. Run safe command `echo hello` - should be ALLOWED
