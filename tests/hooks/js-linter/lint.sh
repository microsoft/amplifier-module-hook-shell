#!/bin/bash
# JavaScript/TypeScript linter hook - runs eslint and injects errors
set -e

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

# Only process JS/TS files
if [[ -z "$FILE_PATH" ]] || [[ ! "$FILE_PATH" =~ \.(js|jsx|ts|tsx)$ ]]; then
    exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Run eslint
LINT_OUTPUT=""
if command -v eslint &> /dev/null; then
    LINT_OUTPUT=$(eslint "$FILE_PATH" --format stylish 2>&1) || true
elif command -v npx &> /dev/null; then
    LINT_OUTPUT=$(npx eslint "$FILE_PATH" --format stylish 2>&1) || true
else
    exit 0
fi

if [[ -n "$LINT_OUTPUT" ]] && [[ "$LINT_OUTPUT" != *"0 problems"* ]]; then
    cat <<EOF
{
  "decision": "approve",
  "reason": "ESLint found issues",
  "contextInjection": "JavaScript/TypeScript linting issues in $FILE_PATH:\n$LINT_OUTPUT\n\nPlease address these issues."
}
EOF
else
    echo '{"decision": "approve", "reason": "No linting issues found"}'
fi
