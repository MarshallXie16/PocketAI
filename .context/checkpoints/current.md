# Checkpoint

**Timestamp:** 2026-07-01T23:10 (local)
**Ticket:** overhaul tasks #1–#8 (see TaskList)
**Phase:** implementation
**Progress:** Phases 0–1 COMPLETE + merged to master. design.md delivered. Phase 2 starting.

## Current Position
Phase 1 merged (`5473873`): env-driven config, all BUG-1..12 + 5 unaudited bugs fixed, deps pinned (venv at `.venv/`), logging, lazy clients, .env.example. Details: `.context/sprints/bootstrap/phase-1-stabilize.md`. Backlog has pre-launch deferrals (LAUNCH-1..5).

## Last Decision
Delegate Phase 2 (monolith carve) to an Opus subagent with a precise brief — keeps orchestrator context lean for phases 3–4; I review + merge.

## Blockers
None. UI work waits on Cloud Design (maintainer has design.md).

## What's Next
1. Phase 2 (task #4): blueprints + services split on branch `phase-2-modularize`; tests (conftest + BUG-x regressions + fix stale date tests); docs/architecture.md + README; CI; delete dead code. Route PATHS must not change (frontend fetch URLs).
2. Then Phase 3 (task #5): docs-first provider adapters (NO Fable in registry), hand-rolled tool loop, pgvector, ConversationState, ThreadPoolExecutor.
3. Then Phase 4a/4b/4c (tasks #6–8) per roadmap.

## Uncommitted State
Clean tree on master. Both branches exist locally; push pending (gh account switch to MarshallXie16 required).
