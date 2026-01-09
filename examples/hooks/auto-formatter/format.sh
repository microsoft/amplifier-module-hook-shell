#!/bin/bash
# Auto Formatter
# Automatically formats code files after editing

# Read JSON from stdin
input=$(cat)

# Extract file path
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

# Skip if no file path
if [[ -z "$file_path" || "$file_path" == "null" ]]; then
    exit 0
fi

# Format based on file type
case "$file_path" in
    *.py)
        if command -v black &> /dev/null; then
            black "$file_path" 2>&1 | head -n 1
            echo "✓ Formatted Python file: $file_path"
        fi
        ;;
    *.js|*.ts|*.jsx|*.tsx)
        if command -v prettier &> /dev/null; then
            prettier --write "$file_path" &> /dev/null
            echo "✓ Formatted JavaScript/TypeScript file: $file_path"
        fi
        ;;
    *.go)
        if command -v gofmt &> /dev/null; then
            gofmt -w "$file_path"
            echo "✓ Formatted Go file: $file_path"
        fi
        ;;
    *.rs)
        if command -v rustfmt &> /dev/null; then
            rustfmt "$file_path"
            echo "✓ Formatted Rust file: $file_path"
        fi
        ;;
esac

exit 0
