# Retrospective — Bootstrap Sprint (the full overhaul, 2026-07-01 → 07-02)

What was planned as "secure + pick a direction" absorbed the entire overhaul in one sustained run: Phases 0–4 all shipped and merged.

## What shipped
- Phase 0: secrets purged from a PUBLIC repo's history (incl. an unaudited Stripe webhook secret + __pycache__), force-pushed; backup + escape-hatch bundle kept.
- Phase 1: env-driven config, 12 audited + 5 unaudited bugs fixed, deps pinned, logging.
- Phase 2: monolith → factory/blueprints/services; tests + docs + CI born.
- Phase 3: provider adapters (docs-first, SDK-verified), hand-rolled tool loop w/ confirmation gate, DB episodic-ready memory, cookie state → DB.
- Phase 4: episodic memory + relationship model + agent-scheduled proactive outreach + voice I/O backend.
- Deliverables: design.md → Cloud Design; 177 tests (was 3 passing); reviews on every phase (1 native + 1 codex).

## What went well
- **Dual reviews earned their cost every phase**: codex caught the immediate-execution injection hole and the double-delivery race; native review caught silent memory loss and the SKIP-gate near-miss; a TEST agent found the streak off-by-one. Different lenses, different catches — none overlapped.
- **Docs-first for provider APIs**: the research brief (SDK-source-verified) made three adapters land right the first time; the one flagged-unverifiable item (SpeechConfig nesting) was verified against the installed SDK before use.
- **Delegation split** (architecture in the main loop, scoped grunt work to opus/sonnet/codex) kept quality high and context manageable across a very long session.

## What didn't / lessons
- An early attempt to delegate ALL of Phase 2 to one agent was (rightly) interrupted by the maintainer — the split model came from that correction. Lesson encoded in memory.
- Research agents without web access can hallucinate confidently ("Sonnet 5 supersedes 4.6") — cross-check model claims against environment truth before adopting.
- sed-based bulk edits bit twice (docstring self-references, test string drift). For >5 mechanical edits, a Python script with exact-match asserts is safer.
- Everything is mock-verified only; live-key verification (LAUNCH-6) is the single biggest unknown.

## Velocity
~40 commits, 4 phase merges, ~180 tests, 2 external + 4 native reviews, in one session. The .context/ + notepad discipline held up across compaction risk.

## Next sprint proposal
**`launch-prep`**: LAUNCH-1..6 from backlog (CSRF, hardening, deploy target, IP-roster/uncensored decision, Alembic baseline, live-key verification) + UI-1..4 integration when Cloud Design returns. Tier 3 — needs maintainer sign-off on scope and the LAUNCH-4 content decisions.
