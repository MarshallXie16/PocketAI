# Task Notepad — Phase 4: Companion Features

**Tickets:** tasks #6/#7/#8 · **Branch:** `phase-4-companion` · **Status:** COMPLETE (2026-07-02) — merged to master

## What landed
- **4a Episodic memory:** JSON retrospective (Haiku tier) extracts episodes (situation/tone/insight/importance/tags) + structured KeyFacts + tone notes; composite recall scoring (0.6 sim / 0.15 recency 30d-half-life / 0.10 reinforcement capped / 0.15 importance) with access write-back. RelationshipState (streaks, tone_prefs) + context_block in the system prompt.
- **4b Proactive outreach:** ScheduledMessage + three sources (daily check-in materialization, in-chat `schedule_checkin` tool, ~daily planner for calendar-experiment opt-ins) → `/tasks/proactive-tick` (X-Tick-Secret, fail-closed) → SKIP-gated in-character delivery as Message(initiated=True). Server-side: consent required, quiet hours (incl. midnight wrap), daily cap counts DELIVERED messages, claim-before-deliver (`pending→processing` conditional update) prevents double-delivery across overlapping ticks, bounded batch/tick, rollback-before-fail-status prevents wedging, scheduling quotas (≤10 pending/pair, ≤30d horizon, no past, ±1h dedupe).
- **4c Voice:** `/transcribe` (gpt-4o-transcribe, ext allowlist, app-level MAX_CONTENT_LENGTH 20MB, review-before-send) + Gemini TTS primary (`gemini-3.1-flash-tts-preview`, SpeechConfig nesting VERIFIED against installed google-genai 2.10.0, PCM→WAV w/ mime-reported rate) with automatic OpenAI fallback.

## Reviews (native opus + codex gpt-5.5) — all findings fixed
Reviewer-found bugs of note: retrospective/planner LLM-JSON type confusion (importance='high' crash → coercion map), tick session poisoning (missing rollbacks), double-delivery race (→ claim), schedule_checkin spam surface (→ quotas), trigger_context prompt injection into delivery (→ delimited as untrusted), SKIP gate too strict ('SKIP.' would have been SENT to the user), daily-cap evasion via backdated scheduled_for, first-interaction streak off-by-one (column default made the None branch dead — found by the TEST agent).
Accepted-risk (documented, low): KeyFact/tone content is user-derived text in the system prompt — self-injection only, tools are user-scoped; sanitized (single line, capped). Escalates if facts ever become cross-user.

## Deferred (in backlog)
- Frontend mic wiring + initiated-message UI + onboarding consent step → waits for Cloud Design return.
- Tick as a real job queue + per-user fairness beyond caps; DST-ambiguous check-in times (zoneinfo fold handling).
- 177 tests green with zero keys; REAL-KEY end-to-end (live chat turn, tool round-trips, TTS/STT) still unverified — needs maintainer's .env.
