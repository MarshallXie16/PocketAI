#!/bin/bash
# UserPromptSubmit hook: inject context reminders and dynamic sprint/task pointers
# Reads static reminders from .agent/hooks/reminders.md
# Receives JSON on stdin, outputs JSON on stdout with additionalContext
# Exit 0: success | Exit 2: blocking error | Other: non-blocking error

set -e

# Source shared library
source "$(dirname "$0")/lib.sh"

# Try to get env vars set by session-start.sh
active_sprint="$ACTIVE_SPRINT_PATH"
declare -a active_task_paths

# Parse colon-separated task paths from env var
if [ -n "$ACTIVE_TASK_PATHS" ]; then
  IFS=':' read -ra active_task_paths <<< "$ACTIVE_TASK_PATHS"
fi

# If no active sprint from env, do a fresh scan using library function
if [ -z "$active_sprint" ]; then
  find_active_sprint
  if [ -n "$ACTIVE_SPRINT" ]; then
    active_sprint=$(to_relative "$ACTIVE_SPRINT")
  fi
fi

# If no tasks from env, scan for in-progress tasks using library function
if [ ${#active_task_paths[@]} -eq 0 ]; then
  find_in_progress_tasks
  for task_file in "${IN_PROGRESS_TASKS[@]}"; do
    active_task_paths+=("$(to_relative "$task_file")")
  done
fi

# Build the additionalContext string
context_lines=()

# Add sprint and task pointers if found (dynamic context)
if [ -n "$active_sprint" ]; then
  context_lines+=("Active sprint: $active_sprint — read this to see current tickets and progress.")
fi

if [ ${#active_task_paths[@]} -gt 0 ]; then
  if [ ${#active_task_paths[@]} -eq 1 ]; then
    context_lines+=("In-progress task: ${active_task_paths[0]} — read this to resume where we left off.")
  else
    context_lines+=("In-progress tasks:")
    for task_path in "${active_task_paths[@]}"; do
      context_lines+=("  - $task_path")
    done
  fi
fi

if [ -n "$active_sprint" ] || [ ${#active_task_paths[@]} -gt 0 ]; then
  context_lines+=("")
fi

# Load static reminders from markdown file
reminders_file="$PROJECT_DIR/.claude/hooks/reminders.md"
if [ -f "$reminders_file" ]; then
  context_lines+=("$(cat "$reminders_file")")
else
  # Fallback if reminders.md doesn't exist (shouldn't happen in normal operation)
  context_lines+=("Key reminders:")
  context_lines+=("- Investigate thoroughly before planning. Do NOT plan or write code without understanding the problem first.")
  context_lines+=("- Plan your changes before implementing. Multi-agent reviews occur at plan and review stages.")
  context_lines+=("- Keep your task notepad up to date as you work. Anything not written down can be lost to compaction.")
  context_lines+=("- If you don't have a task notepad for the current work, create one from .claude/templates/notepad.md.")
  context_lines+=("- Consult .claude/rules/ before working in an area — rules are path-scoped and auto-loaded when matching files are opened.")
  context_lines+=("- Update documentation after significant changes.")
  context_lines+=("- Request code review after implementing (at least 1 native + 1 external subagent).")
  context_lines+=("- Think iteratively: investigate → plan → implement → test → review.")
fi

# Join all lines with newlines
additionalContext=$(printf '%s\n' "${context_lines[@]}")

# Build JSON output
require_jq
output=$(jq -n \
  --arg additionalContext "$additionalContext" \
  '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $additionalContext
    }
  }')

echo "$output"
exit 0
