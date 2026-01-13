---
bundle:
  name: test-linters
  version: 0.1.0
  description: Test bundle for Python and JS linter hooks with context injection

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

hooks:
  - module: hook-shell
    source: git+https://github.com/robotdad/amplifier-module-hook-shell@main
    config:
      hooks_dirs:
        - .amplifier/hooks
---

# Test Bundle: Linters

This bundle tests the Python and JS linter hooks that inject feedback into agent context.

## Hooks Included

Copy the linter hooks to your project:

```bash
cp -r tests/hooks/python-linter .amplifier/hooks/
cp -r tests/hooks/js-linter .amplifier/hooks/
```

## Expected Behavior

- **PostToolUse on Edit/Write**: After editing `.py` files, ruff check runs
- **contextInjection**: If linting errors found, they're injected into agent context
- Agent sees linting issues and can fix them in the same turn

## Test Cases

1. Create Python file with linting errors (unused import) - should inject context
2. Create clean Python file - should pass silently
3. Create JS file with ESLint errors - should inject context
