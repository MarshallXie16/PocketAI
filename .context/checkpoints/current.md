# Checkpoint

**Timestamp:** 2026-07-02T03:30 (local)
**Ticket:** overhaul COMPLETE (tasks #1–#8 all done)
**Phase:** review/wrap-up
**Progress:** Phases 0–4 merged to master and pushed (`2191e19`). 177 tests green, ruff clean.

## Current Position
The full overhaul is done. All phase branches pushed. Retro written (`.context/sprints/bootstrap/retro.md`). Backlog restructured: LAUNCH-1..6 (pre-launch), UI-1..4 (waiting on Cloud Design), DEBT-5..7.

## Last Decision
Next sprint proposed as `launch-prep` (Tier 3 — awaiting maintainer sign-off): LAUNCH items + UI integration when the Cloud Design UI returns.

## Blockers
- **Maintainer**: send `docs/designs/design.md` §8 to Cloud Design (if not already); provide .env for LAUNCH-6 live-key verification; decide LAUNCH-4 (IP roster / uncensored).
- Proactive features are DORMANT until UI-3 ships (no UI sets proactive_consent_at yet) — by design, consent-first.

## What's Next (new session)
1. Read CLAUDE.local.md → this file → `.context/backlog.md`.
2. If maintainer approved `launch-prep`: start with LAUNCH-5 (Alembic baseline — all models final) and LAUNCH-1 (CSRF), both key-free.
3. If Cloud Design returned: UI-1..4 integration against the documented endpoints.
4. If .env available: LAUNCH-6 live verification FIRST (it gates everything else).

## Uncommitted State
Context files (backlog, retro, this checkpoint, phase-4 notepad) — committing now.
