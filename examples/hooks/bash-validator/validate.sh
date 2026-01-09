#!/bin/bash
# Bash Command Validator
# Blocks dangerous bash commands before execution

# Read JSON from stdin
input=$(cat)

# Extract command
command=$(echo "$input" | jq -r '.tool_input.command')

# Block dangerous commands
dangerous=("rm -rf /" "dd if=" "mkfs" ":(){ :|:& };:")

for pattern in "${dangerous[@]}"; do
    if [[ "$command" == *"$pattern"* ]]; then
        echo "{\"decision\": \"block\", \"reason\": \"Dangerous command blocked: $pattern\", \"systemMessage\": \"⛔ Security: Blocked dangerous operation\"}" 
        exit 2
    fi
done

# Allow command
exit 0
