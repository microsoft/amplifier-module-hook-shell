#!/bin/bash
# Python linter hook - runs ruff check and injects errors into agent context
set -e

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

# Only process Python files
if [[ -z "$FILE_PATH" ]] || [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Run ruff check
if command -v ruff &> /dev/null; then
    LINT_OUTPUT=$(ruff check "$FILE_PATH" 2>&1) || true
    
    if [[ -n "$LINT_OUTPUT" ]]; then
        # Escape for JSON
        ESCAPED_OUTPUT=$(echo "$LINT_OUTPUT" | jq -Rs .)
        
        # Inject linting errors into agent context
        cat <<EOF
{
  "decision": "approve",
  "reason": "Linting completed with issues found",
  "contextInjection": "Python linting issues found in $FILE_PATH:\n$LINT_OUTPUT\n\nPlease fix these issues."
}
EOF
    else
        echo '{"decision": "approve", "reason": "No linting issues found"}'
    fi
else
    exit 0
fi
