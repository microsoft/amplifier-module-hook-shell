#!/bin/bash
# JavaScript/TypeScript formatter hook - runs prettier on edited files
set -e

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

# Only process JS/TS files
if [[ -z "$FILE_PATH" ]] || [[ ! "$FILE_PATH" =~ \.(js|jsx|ts|tsx|json)$ ]]; then
    exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Run prettier
if command -v prettier &> /dev/null; then
    prettier --write "$FILE_PATH" 2>/dev/null || true
    echo '{"decision": "approve", "reason": "Formatted with prettier"}'
elif command -v npx &> /dev/null; then
    npx prettier --write "$FILE_PATH" 2>/dev/null || true
    echo '{"decision": "approve", "reason": "Formatted with prettier via npx"}'
else
    exit 0
fi
