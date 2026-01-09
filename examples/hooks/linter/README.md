# Linter Hook

Runs linter after file edits and injects feedback into the agent's context for automatic correction.

## Supported Languages

- **Python**: Uses `pylint`
- **JavaScript/TypeScript**: Uses `eslint`

## Installation

```bash
cp -r examples/hooks/linter .amplifier/hooks/
chmod +x .amplifier/hooks/linter/lint.py
```

## Requirements

Install linters for the languages you use:

```bash
# Python
pip install pylint

# JavaScript/TypeScript
npm install -g eslint
```

## How It Works

1. After the agent edits or writes a file, this hook runs
2. The appropriate linter is executed based on file extension
3. If issues are found, they're injected into the agent's context
4. The agent can see the issues and fix them in the same turn

## Example Output

When linting issues are found:
```
⚠️ Linting issues detected in main.py
```

The agent will receive detailed linting output and can address issues immediately.
