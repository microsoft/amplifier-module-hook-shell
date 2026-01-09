#!/bin/bash
# File guard hook - blocks writes to protected paths

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Protected patterns (customize as needed)
PROTECTED_PATTERNS=(
    "^/etc/"
    "^/usr/"
    "^/bin/"
    "^/sbin/"
    "\.env$"
    "\.env\.local$"
    "secrets\.yaml$"
    "credentials\."
    "\.pem$"
    "\.key$"
    "id_rsa"
    "id_ed25519"
)

# Check against protected patterns
for pattern in "${PROTECTED_PATTERNS[@]}"; do
    if [[ "$FILE_PATH" =~ $pattern ]]; then
        cat <<EOF
{
  "decision": "block",
  "reason": "File path matches protected pattern: $pattern",
  "systemMessage": "Blocked: Cannot write to protected file '$FILE_PATH'. This path is protected by file-guard hook."
}
EOF
        exit 2
    fi
done

# Allow the operation
exit 0
