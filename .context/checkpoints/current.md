# Checkpoint

**Timestamp:** 2026-07-02T01:30 (local)
**Ticket:** tasks #6–#8 (Phase 4)
**Phase:** implementation
**Progress:** Phases 0–3 COMPLETE + merged + pushed. Phase 4a starting.

## Current Position
Phase 3 merged (`bcfe6bc`): provider adapters (Anthropic/OpenAI/google-genai; NO Fable), hand-rolled tool loop with server-side confirm gate for consequential actions, DB memory store (cosine, pgvector-ready), ConversationState (short-term memory out of cookie), background executor, legacy components/ deleted. 130 tests green, ruff clean. Reviews: codex verified adapter shapes against installed SDKs; all findings fixed (see `.context/sprints/bootstrap/phase-3-modernize-ai.md`).

## Last Decision
Confirm-gate design: consequential tools store drafts in ConversationState.pending_action; confirm_action executes only if a genuine user message postdates the draft (same-turn injection cannot self-confirm).

## Blockers
None. Live-key verification (real chat turn + tool round-trip) pending maintainer's .env.

## What's Next
1. Phase 4a (task #6): episodic memory scoring (composite: 0.6 sim + 0.15 recency + 0.10 reinforcement + 0.15 importance — fields already on MemoryEntry), Haiku retrospective extraction of episodes + key_facts, relationship_state table + RelationshipService.context_block() into the system prompt (agent.run_turn already accepts relationship_block).
2. Phase 4b (task #7): scheduled_message + schedule_checkin tool + /tasks/proactive-tick + nightly planner. Reuse the confirm-gate patterns.
3. Phase 4c (task #8): /transcribe (gpt-4o-transcribe) + MediaRecorder wiring; Gemini TTS behind TTSProvider (research brief §2.9/§3 has call shapes).
4. Docs pass: architecture.md still references deleted components/.

## Uncommitted State
Clean. Branches master/phase-1/2/3 pushed. Working on master → cut phase-4-companion next.
