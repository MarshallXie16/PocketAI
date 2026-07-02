# Checkpoint

**Timestamp:** 2026-07-01T22:05 (local)
**Ticket:** bootstrap sprint / overhaul kickoff
**Phase:** implementation
**Progress:** Phase 0 (purge) complete; Phase 1 starting.

## Current Position
Overhaul plan approved by maintainer (roadmap: `docs/designs/overhaul-roadmap.md`; quick-orient: `CLAUDE.local.md`). Phase 0 executed: backup at `~/pocketai-secure-backup-2026-07-01/`, git-filter-repo purged DBs + scrubbed Azure/ElevenLabs/Stripe-whsec keys + __pycache__, force-pushed (`df1cad0`). Task list #1–#8 tracks phases.

## Last Decision
Scrubbed literal key strings with --replace-text instead of dropping text_to_speech.py history (keeps file history; neutralizes secrets even if maintainer skips rotation). Found + scrubbed an unaudited Stripe webhook secret.

## Blockers
None. (UI implementation waits on Cloud Design returning the new design — backend-only until then.)

## What's Next
1. Write `docs/designs/design.md` (branding + Cloud Design build prompt) — early deliverable so maintainer can send it off (task #2).
2. Phase 1 (task #3): config.py rewrite + app factory + BUG-1..12 fixes + deps + logging; Alembic baseline LAST (after all model edits incl. Phase-4 tables — see roadmap risk #1).
3. Then Phase 2 modularization.

## Uncommitted State
Untracked: `docs/designs/overhaul-roadmap.md` (copied plan), `CLAUDE.local.md` (gitignored). Modified: `.context/sprints/bootstrap/sprint.md`, checkpoint. Commit context updates with next work commit.
