#!/bin/bash
# Post-tool logger - logs command result after execution

INPUT=$(cat)
LOG_FILE="${AMPLIFIER_PROJECT_DIR:-.}/.amplifier/command-log.jsonl"

mkdir -p "$(dirname "$LOG_FILE")"

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // "unknown"')
RESULT=$(echo "$INPUT" | jq -r '.tool_result // "no result"' | head -c 500)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Log entry with truncated result
echo "{\"timestamp\": \"$TIMESTAMP\", \"event\": \"post_execute\", \"command\": $(echo "$COMMAND" | jq -Rs .), \"result_preview\": $(echo "$RESULT" | jq -Rs .)}" >> "$LOG_FILE"

exit 0
