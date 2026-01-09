# Auto Formatter

Automatically formats code files after editing based on file type.

## Supported Languages

- **Python**: Uses `black`
- **JavaScript/TypeScript**: Uses `prettier`
- **Go**: Uses `gofmt`
- **Rust**: Uses `rustfmt`

## Installation

```bash
cp -r examples/hooks/auto-formatter .amplifier/hooks/
chmod +x .amplifier/hooks/auto-formatter/format.sh
```

## Requirements

Install the formatters for the languages you use:

```bash
# Python
pip install black

# JavaScript/TypeScript
npm install -g prettier

# Go (included with Go)
# Rust (included with Rust)
```

## Customization

Edit `format.sh` to add more file types or change formatting commands.
