#!/bin/bash
# Shared library for agent framework hooks
# Source this file: source "$(dirname "$0")/lib.sh"

# Resolve project root
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Extract status value from YAML frontmatter
# Handles both quoted and unquoted values, searches first 5 lines
# Usage: status=$(extract_status "$filepath")
extract_status() {
  local filepath="$1"
  if [ ! -f "$filepath" ]; then
    echo ""
    return
  fi
  head -5 "$filepath" | grep "^status:" | head -1 | \
    sed 's/^[^:]*:[[:space:]]*//' | \
    sed "s/^['\"]//; s/['\"]$//"
}

# Find the active sprint file (status: active in frontmatter)
# Sets ACTIVE_SPRINT to the file path, or empty string if none found
# Usage: find_active_sprint; echo "$ACTIVE_SPRINT"
find_active_sprint() {
  ACTIVE_SPRINT=""
  if [ -d "$PROJECT_DIR/.context/sprints" ]; then
    for sprint_file in "$PROJECT_DIR/.context/sprints"/*/sprint.md; do
      if [ -f "$sprint_file" ]; then
        local status
        status=$(extract_status "$sprint_file")
        if [ "$status" = "active" ]; then
          ACTIVE_SPRINT="$sprint_file"
          return
        fi
      fi
    done
  fi
}

# Find all in-progress task notepads (in active sprint + ad-hoc tasks)
# Populates IN_PROGRESS_TASKS array
# Usage: find_in_progress_tasks; for t in "${IN_PROGRESS_TASKS[@]}"; do ...; done
find_in_progress_tasks() {
  IN_PROGRESS_TASKS=()

  # Check active sprint directory
  if [ -n "$ACTIVE_SPRINT" ]; then
    local sprint_dir
    sprint_dir=$(dirname "$ACTIVE_SPRINT")
    for task_file in "$sprint_dir"/*.md; do
      if [ -f "$task_file" ] && [ "$task_file" != "$ACTIVE_SPRINT" ]; then
        local status
        status=$(extract_status "$task_file")
        if [ "$status" = "in-progress" ]; then
          IN_PROGRESS_TASKS+=("$task_file")
        fi
      fi
    done
  fi

  # Check ad-hoc tasks
  if [ -d "$PROJECT_DIR/.context/tasks" ]; then
    for task_file in "$PROJECT_DIR/.context/tasks"/*.md; do
      if [ -f "$task_file" ]; then
        local status
        status=$(extract_status "$task_file")
        if [ "$status" = "in-progress" ]; then
          IN_PROGRESS_TASKS+=("$task_file")
        fi
      fi
    done
  fi
}

# Persist active sprint/task paths to CLAUDE_ENV_FILE for other hooks
# Usage: persist_to_env
persist_to_env() {
  if [ -z "$CLAUDE_ENV_FILE" ]; then
    return
  fi

  if [ -n "$ACTIVE_SPRINT" ]; then
    local rel_sprint="${ACTIVE_SPRINT#$PROJECT_DIR/}"
    echo "export ACTIVE_SPRINT_PATH='$rel_sprint'" >> "$CLAUDE_ENV_FILE"
  fi

  if [ ${#IN_PROGRESS_TASKS[@]} -gt 0 ]; then
    local task_paths=""
    for task_file in "${IN_PROGRESS_TASKS[@]}"; do
      local rel_task="${task_file#$PROJECT_DIR/}"
      if [ -z "$task_paths" ]; then
        task_paths="$rel_task"
      else
        task_paths="$task_paths:$rel_task"
      fi
    done
    echo "export ACTIVE_TASK_PATHS='$task_paths'" >> "$CLAUDE_ENV_FILE"
  fi
}

# Convert absolute path to relative (relative to project root)
# Usage: rel=$(to_relative "$absolute_path")
to_relative() {
  echo "${1#$PROJECT_DIR/}"
}

# Check if jq is available (required for JSON output)
require_jq() {
  if ! command -v jq &>/dev/null; then
    echo '{"error": "jq not found — hook cannot construct JSON output"}' >&2
    exit 2
  fi
}
