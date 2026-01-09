#!/bin/bash
# Pre-tool logger - logs command before execution

INPUT=$(cat)
LOG_FILE="${AMPLIFIER_PROJECT_DIR:-.}/.amplifier/command-log.jsonl"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Extract command
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // "unknown"')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Log entry
echo "{\"timestamp\": \"$TIMESTAMP\", \"event\": \"pre_execute\", \"command\": $(echo "$COMMAND" | jq -Rs .)}" >> "$LOG_FILE"

# Always approve (this is just logging)
exit 0
