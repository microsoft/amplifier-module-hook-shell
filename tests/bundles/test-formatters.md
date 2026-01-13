---
bundle:
  name: test-formatters
  version: 0.1.0
  description: Test bundle for Python and JS formatter hooks

includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main

hooks:
  - module: hook-shell
    source: git+https://github.com/robotdad/amplifier-module-hook-shell@main
    config:
      hooks_dirs:
        - .amplifier/hooks
---

# Test Bundle: Formatters

This bundle tests the Python and JS formatter hooks.

## Hooks Included

When using this bundle, copy the formatter hooks to your project:

```bash
cp -r tests/hooks/python-formatter .amplifier/hooks/
cp -r tests/hooks/js-formatter .amplifier/hooks/
```

## Expected Behavior

- **PostToolUse on Edit/Write**: After editing `.py` files, ruff format runs automatically
- **PostToolUse on Edit/Write**: After editing `.js/.ts` files, prettier runs automatically

## Test Cases

1. Create a Python file with bad formatting - should auto-format
2. Create a JS file with bad formatting - should auto-format
3. Edit a non-Python/JS file - should do nothing
