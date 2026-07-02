#!/bin/bash
# PreCompact hook: remind to update task notepad before compaction
# Receives JSON on stdin, outputs JSON on stdout with systemMessage
# Exit 0: success | Exit 2: blocking error | Other: non-blocking error

set -e

# Source shared library
source "$(dirname "$0")/lib.sh"

# Check if there's an active task or sprint
has_active_work=0
task_notepad=""

# Try env vars from session-start
if [ -n "$ACTIVE_TASK_PATHS" ]; then
  # Get first task path from colon-separated string
  task_notepad="$PROJECT_DIR/${ACTIVE_TASK_PATHS%%:*}"
  has_active_work=1
elif [ -n "$ACTIVE_SPRINT_PATH" ]; then
  has_active_work=1
fi

# If no env vars, do a fresh scan
if [ $has_active_work -eq 0 ]; then
  find_active_sprint
  find_in_progress_tasks

  if [ -n "$ACTIVE_SPRINT" ]; then
    has_active_work=1
  fi

  if [ ${#IN_PROGRESS_TASKS[@]} -gt 0 ]; then
    task_notepad="${IN_PROGRESS_TASKS[0]}"
  fi
fi

# Build system message — short, urgent, concrete checklist (per design spec)
systemMessage="Compaction imminent. Write down anything your future self needs to resume. Update your task notepad NOW with at minimum:\n- Current phase and what you're working on\n- Key findings and decisions made so far\n- Concrete next steps\n- Any open questions or blockers"

if [ -n "$task_notepad" ]; then
  systemMessage="$systemMessage\n\nTask notepad: $task_notepad"
fi

# Build JSON output with systemMessage
# Note: PreCompact doesn't support additionalContext, only systemMessage
require_jq
output=$(jq -n \
  --arg msg "$systemMessage" \
  '{systemMessage: $msg}')

echo "$output"
exit 0
