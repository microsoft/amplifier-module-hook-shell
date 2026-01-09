#!/bin/bash
# Python formatter hook - runs ruff format on edited Python files
set -e

# Read input from stdin
INPUT=$(cat)

# Extract the file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

# Only process Python files
if [[ -z "$FILE_PATH" ]] || [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi

# Check if file exists
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Run ruff format
if command -v ruff &> /dev/null; then
    ruff format "$FILE_PATH" 2>/dev/null || true
    
    # Output success message
    echo '{"decision": "approve", "reason": "Formatted Python file with ruff"}'
else
    # ruff not installed, skip silently
    exit 0
fi
