#!/bin/bash
# SessionStart hook: discover active sprint and in-progress tasks
# Supports two matchers:
#   - startup|resume: Full orientation with additionalContext
#   - compact: Called by post-compaction.sh (legacy, kept for compatibility)
# Receives JSON on stdin, outputs JSON on stdout
# Exit 0: success | Exit 2: blocking error | Other: non-blocking error

set -e

# Source shared library
source "$(dirname "$0")/lib.sh"

# Determine matcher type from environment (set by Claude Code)
# If not set, default to full orientation
MATCHER_TYPE="${HOOK_MATCHER_TYPE:-startup}"

# Initialize output
hookOutput='{"hookSpecificOutput": {}}'

# Find active sprint and in-progress tasks using shared functions
find_active_sprint
find_in_progress_tasks

# Persist to environment file for other hooks
persist_to_env

# Build additionalContext for startup|resume matcher
if [ "$MATCHER_TYPE" = "startup" ] || [ "$MATCHER_TYPE" = "resume" ]; then
  context_lines=()

  # Core orientation
  context_lines+=("Read .context/project.md for project context. Check .claude/rules/ for learned patterns relevant to your current work.")
  context_lines+=("")

  # Add sprint and task pointers if found
  if [ -n "$ACTIVE_SPRINT" ]; then
    rel_sprint=$(to_relative "$ACTIVE_SPRINT")
    context_lines+=("Active sprint: $rel_sprint — read this to see current tickets and progress.")
  fi

  if [ ${#IN_PROGRESS_TASKS[@]} -gt 0 ]; then
    if [ ${#IN_PROGRESS_TASKS[@]} -eq 1 ]; then
      rel_task=$(to_relative "${IN_PROGRESS_TASKS[0]}")
      context_lines+=("In-progress task: $rel_task — read this to resume where we left off.")
    else
      context_lines+=("In-progress tasks:")
      for task_file in "${IN_PROGRESS_TASKS[@]}"; do
        rel_task=$(to_relative "$task_file")
        context_lines+=("  - $rel_task")
      done
    fi
  fi

  if [ -n "$ACTIVE_SPRINT" ] || [ ${#IN_PROGRESS_TASKS[@]} -gt 0 ]; then
    context_lines+=("")
    context_lines+=("Brief orientation: You are resuming work on an active project. Review sprint progress and task status, then continue from where you left off.")
  fi

  # Join all lines with newlines
  additionalContext=$(printf '%s\n' "${context_lines[@]}")

  # Update JSON output to include additionalContext
  require_jq
  hookOutput=$(jq -n \
    --arg additionalContext "$additionalContext" \
    '{
      hookSpecificOutput: {
        hookEventName: "SessionStart",
        additionalContext: $additionalContext
      }
    }')
fi

# Output JSON
echo "$hookOutput"
exit 0
