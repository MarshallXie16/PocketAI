#!/bin/bash
# Stop hook: validate that context files were updated before stopping
# Receives JSON on stdin with session metadata, outputs JSON on stdout
# Exit 0: success (allow stop) | Exit 2: blocking error | Other: non-blocking error

set -e

# Source shared library
source "$(dirname "$0")/lib.sh"

# Read JSON input (session metadata)
input=$(cat)

# Helper function: check if file was modified during this session
# Uses git to detect uncommitted changes, falls back to mtime heuristic
was_modified_this_session() {
  local filepath="$1"
  if [ ! -f "$filepath" ]; then
    return 1
  fi

  # If inside a git repo, check for uncommitted changes (most reliable)
  if command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    # Staged or unstaged changes to this file
    if git diff --name-only -- "$filepath" 2>/dev/null | grep -q . || \
       git diff --cached --name-only -- "$filepath" 2>/dev/null | grep -q .; then
      return 0
    fi
    # Untracked file (newly created this session)
    if git ls-files --others --exclude-standard -- "$filepath" 2>/dev/null | grep -q .; then
      return 0
    fi
    return 1
  fi

  # Fallback: check if modified in the last 2 hours (rough session heuristic)
  local file_mtime
  file_mtime=$(stat -c%Y "$filepath" 2>/dev/null || stat -f%m "$filepath" 2>/dev/null || echo 0)
  local now
  now=$(date +%s)
  local two_hours=7200

  if [ "$file_mtime" -gt 0 ] && [ $((now - file_mtime)) -lt $two_hours ]; then
    return 0
  fi

  return 1
}

# Find active sprint and task
active_sprint=""
task_notepad=""

# Check environment variables from session-start
if [ -n "$ACTIVE_SPRINT_PATH" ]; then
  active_sprint="$PROJECT_DIR/$ACTIVE_SPRINT_PATH"
fi

if [ -n "$ACTIVE_TASK_PATHS" ]; then
  # Get first task path from colon-separated string
  task_notepad="$PROJECT_DIR/${ACTIVE_TASK_PATHS%%:*}"
fi

# If env vars not set, do a fresh scan
if [ -z "$active_sprint" ]; then
  find_active_sprint
  if [ -n "$ACTIVE_SPRINT" ]; then
    active_sprint="$ACTIVE_SPRINT"
  fi
fi

# Find task notepad if not set
if [ -z "$task_notepad" ] && [ -n "$active_sprint" ]; then
  find_in_progress_tasks
  if [ ${#IN_PROGRESS_TASKS[@]} -gt 0 ]; then
    task_notepad="${IN_PROGRESS_TASKS[0]}"
  fi
fi

# If still no task, check ad-hoc tasks (IN_PROGRESS_TASKS already includes them from find_in_progress_tasks)
# The find_in_progress_tasks function already covers ad-hoc tasks, so no additional scan needed

# Determine if we should block the stop
should_block=0
block_reason=""

# Only block if there's active work but context files weren't updated
if [ -n "$active_sprint" ] || [ -n "$task_notepad" ]; then
  files_updated=0

  # Check if sprint file was updated
  if [ -n "$active_sprint" ] && was_modified_this_session "$active_sprint"; then
    files_updated=1
  fi

  # Check if task notepad was updated
  if [ -n "$task_notepad" ] && was_modified_this_session "$task_notepad"; then
    files_updated=1
  fi

  # If no files were updated and there's active work, block
  if [ $files_updated -eq 0 ]; then
    should_block=1
    block_reason="Active work detected but context files not updated. Before stopping:\n1. Update sprint file: ticket statuses, progress log entry, current task pointer.\n2. Update task notepad: current phase, findings, decisions, next steps — enough for a new session to resume without asking the user.\n3. If you learned a reusable lesson, note it in sprint findings for later discussion.\n4. If you deferred work, add it to backlog.md with source context.\n5. If project architecture or conventions changed, update project.md.\n6. If any context file is approaching its size cap, consolidate it now."
  fi
fi

# Build JSON output
if [ $should_block -eq 1 ]; then
  require_jq
  output=$(jq -n \
    --arg reason "$block_reason" \
    '{decision: "block", reason: $reason}')
  echo "$output"
  exit 2
else
  # Allow stop
  echo "{}"
  exit 0
fi
