# Bash Command Validator

Blocks dangerous bash commands before execution.

## Installation

```bash
cp -r examples/hooks/bash-validator .amplifier/hooks/
chmod +x .amplifier/hooks/bash-validator/validate.sh
```

## Blocked Patterns

- `rm -rf /`
- `dd if=`
- `mkfs`
- Fork bombs: `:(){ :|:& };:`

## Customization

Edit `validate.sh` to add more patterns to the `dangerous` array.

## Testing

```bash
# This should be blocked
echo '{"tool_input": {"command": "rm -rf /"}}' | ./validate.sh

# This should pass
echo '{"tool_input": {"command": "ls -la"}}' | ./validate.sh
```
