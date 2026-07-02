# Checkpoint

**Timestamp:** 2026-07-01
**Ticket:** (pre-sprint — scaffolding)
**Phase:** planning
**Progress:** Prep package complete; overhaul not yet started.

## Current Position
PocketAI was cloned to `~/PocketAI` and the agent framework (`.claude/` + `CLAUDE.md`) was copied in. A full 4-part codebase audit ran on 2026-07-01. The framework scaffold now exists: `project.md`, `backlog.md`, the `bootstrap` sprint, and `docs/designs/overhaul-and-repositioning.md` (the north-star plan). No application code has been changed.

## Last Decision
Keep the constitution as-is (maintainer's call); adopt a two-track overhaul (technical + strategic repositioning) with security triage first.

## Blockers
- Strategic identity not yet chosen (BOOT-3) — blocks all Track-B feature work.
- Exposed credentials not yet rotated (BOOT-1) — blocks any deploy.

## What's Next
1. Read `.context/project.md`, then `docs/designs/overhaul-and-repositioning.md` for the full picture.
2. Kick off the `bootstrap` sprint: BOOT-1 (rotate exposed creds) and BOOT-3 (confirm direction). Flip sprint `status: planned → active`.
3. After bootstrap, open the `stabilize` sprint from `backlog.md` (Phase 1: config, critical bugs, hardening, deploy target).

## Uncommitted State
New untracked files only: `.claude/`, `CLAUDE.md`, `.context/`, `docs/`. No changes to existing tracked files. Nothing committed yet.
