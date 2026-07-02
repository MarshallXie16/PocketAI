#!/bin/bash
# PostCompaction hook: recovery-focused SessionStart handler after context compaction
# Receives JSON on stdin, outputs JSON on stdout with additionalContext
# Exit 0: success | Exit 2: blocking error | Other: non-blocking error
# This hook is invoked via SessionStart matcher "compact"

set -e

# Source shared library
source "$(dirname "$0")/lib.sh"

# Find active sprint and in-progress tasks using shared functions
find_active_sprint
find_in_progress_tasks

# Persist to environment file for other hooks
persist_to_env

# Build recovery-focused additionalContext
context_lines=()

context_lines+=("Context was just compacted. The summary above may have lost nuance — trust your written files over your own memory of what happened.")
context_lines+=("")
context_lines+=("Read your active task notepad's Current Status section to recover exactly where you left off. Don't ask the user to re-explain anything—your files are your memory.")
context_lines+=("")

# Add sprint and task pointers if found
if [ -n "$ACTIVE_SPRINT" ]; then
  rel_sprint=$(to_relative "$ACTIVE_SPRINT")
  context_lines+=("Active sprint: $rel_sprint")
fi

if [ ${#IN_PROGRESS_TASKS[@]} -gt 0 ]; then
  if [ ${#IN_PROGRESS_TASKS[@]} -eq 1 ]; then
    rel_task=$(to_relative "${IN_PROGRESS_TASKS[0]}")
    context_lines+=("In-progress task: $rel_task — read Current Status section to resume immediately.")
  else
    context_lines+=("In-progress tasks:")
    for task_file in "${IN_PROGRESS_TASKS[@]}"; do
      rel_task=$(to_relative "$task_file")
      context_lines+=("  - $rel_task")
    done
  fi
fi

# Join all lines with newlines
additionalContext=$(printf '%s\n' "${context_lines[@]}")

# Build JSON output with additionalContext
require_jq
output=$(jq -n \
  --arg additionalContext "$additionalContext" \
  '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: $additionalContext
    }
  }')

echo "$output"
exit 0
