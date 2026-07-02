# PocketAI Full Overhaul & Repositioning — Implementation Plan (rev 2)

## Context

PocketAI (~2022–2024) was an agentic AI assistant before agents were a category: personas + persistent memory (Pinecone) + real tool use (Google Calendar/Gmail/contacts) + TTS voice, in a 1,604-line Flask monolith (`app.py`). A prior audit (`docs/designs/overhaul-and-repositioning.md`, `.context/backlog.md`) catalogued everything; this session spot-verified it.

**Maintainer decisions (locked):**
1. **Identity: "a companion that actually acts"** — persistent AI presence with a relationship AND real agency (calendar, email, check-ins, proactive outreach).
2. **Scope: full overhaul, Phases 0–4** — priority on **bugs, maintainability, and pivot features** over production-hardening. Lower-priority prod/security-hardening items go to the backlog (no deploy today; deployment itself deferred). No Sentry.
3. **Committed data: back up locally, then purge tree + history, force-push.**
4. **IP characters + "uncensored" tier: defer, flagged as launch blockers.**
5. **Models: no Fable** (cost) — Opus 4.8 / Sonnet 4.6 / Haiku 4.5 tiers. Read latest provider docs before writing adapters; hand-rolled agent loop, no managed agent frameworks.
6. **Voice: Gemini TTS** (`gemini-3.1-flash-tts-preview` — verified to exist, Apr 2026, 200+ expressive audio tags) with OpenAI TTS fallback.
7. **Memory: adapt a subset of `~/autonomous-agent-research/episodic-memory/design-doc.md`** (read this session) to upgrade the naive Pinecone similarity search.
8. **UI: full redesign** via a branding doc + build prompt (frontend-design skill, no generic AI-slop).

### Why credential rotation is still recommended (answering 0.1)
Verified this session: the GitHub repo **`MarshallXie16/PocketAI` is PUBLIC**. `src/instance/users.db` is in pushed history across 5+ commits and contains 2 Google OAuth rows with plaintext **refresh tokens** (scopes: `gmail.modify` + `calendar` — they grant email/calendar access until revoked or ~6 months unused; the app ran until ~May 2026, so they may still be live). The Azure Speech key is literally readable in history (`git log -p` shows `d031f7f7...` — I retrieved it in one command), same for the ElevenLabs key. Public GitHub is continuously scraped by secret-harvesting bots, so "committed to a public repo" = "exposed," even if the file is deleted later. The fix is cheap: revoke PocketAI's access at myaccount.google.com/permissions for the 2 accounts (~2 min), and regenerate the Azure/ElevenLabs keys **if those accounts still exist** (if the subscriptions are dead, there's nothing to rotate). This is a recommendation with evidence, your call — the purge proceeds either way.

---

## Phase 0 — Data purge (order: [optional revocation] → backup → purge → force-push)

1. **Backup outside repo:** `~/pocketai-secure-backup-2026-07-01/` — `users.db`, `src/db/` (Chroma), full `git bundle` of pre-rewrite history (escape hatch).
2. **Purge:** `git rm --cached` + `git filter-repo --invert-paths` on `src/instance/users.db`, `src/db/`, `save.txt`, `src/deprecated/save.txt`, `src/prototypes/recording.wav`; re-add origin; force-push. Done on `master` BEFORE any phase branches (rewrite changes all hashes).
3. **Verify + harden `.gitignore`:** add `save.txt`, `*.db`, `*.sqlite3`, `*.bin`; confirm `git log --all` is clean; history-wide grep for any other keys.
4. **Encrypt OAuth tokens at rest:** Fernet `EncryptedString` TypeDecorator on `google_user.access_token/refresh_token`, keyed by `TOKEN_ENCRYPTION_KEY` env var (cheap, prevents recurrence; bakes into the fresh migration baseline).

## Phase 1 — Fix the real bugs + sane foundations (rescoped)

**Config/bootstrapping (needed for everything after):** rewrite `config.py` (env-driven `select_config()`, fix `DATABASE_URL` `None.replace` crash, fail-closed prod `SECRET_KEY`); new `src/app_factory.py` + `wsgi.py`; kill import-time `app = create_app()` (`app.py:65`), the pre-`load_dotenv()` `stripe.api_key` ordering bug (`:43` vs `:45`), and import-time boto3/OpenAI/Pinecone client instantiation (→ lazy, factory-owned).

**Genuine bugs (all verified with line refs):**
- BUG-1: remove `GET /add-credits/<amount>` (`app.py:1103`) — any user grants themselves credits.
- BUG-2: `/send_message` decorator order (`:279`, `@login_required` is a no-op) + restore commented `try/except` (`:336`).
- BUG-3: protect `/admin/reset_credits` (`:1110`) — `is_admin` check, constant-time compare, no default password.
- BUG-4 (IDOR): shared `get_owned_ai(user, ai_id)` helper (404 on non-owner) on `/ai-settings/<id>`, `/change-ai/<id>`, `/profile/delete-ai/<id>`.
- BUG-5: Stripe fulfillment — remove `@login_required` from the `handle_checkout_session` helper, pass `user_id` explicitly (webhooks have no session), fix nonexistent `user.credits` → `add_paid_credits()`, idempotency via stored event IDs.
- BUG-6..12: cross-provider attr crash (`ai_models.py:148`), `regenerate_message` unordered delete (`app.py:374`), contacts self-comparison (`email_service.py:230`), never-populated `_service_cache` (per-user, not class-level), input validation on form/JSON handlers, dead `google=None` global, `memory_chunk_size` 6-vs-256 mismatch.
- Credit constants unified in `config.py` (fixes 1500/100/900 inconsistency).

**Foundations:** pin + prune `requirements.txt` (remove desktop-audio libs, Azure stack, elevenlabs, chromadb, pinecone; add `anthropic`, `google-genai`, `beautifulsoup4`, `cryptography`, `pgvector`, `psycopg2-binary`, `Flask-WTF` for validation); delete stale Alembic revisions and autogenerate ONE fresh baseline after all model edits (incl. Phase-4 tables) land; replace `print()` with structured logging + error handlers.

**Deferred to backlog (written to `.context/backlog.md` as pre-launch requirements):** CSRF wiring across templates/fetch, Talisman/cookie hardening/rate limiting, Docker/deploy target, `/health`, Sentry/monitoring, Heroku-vs-EB artifact cleanup decision.

## Phase 2 — Modularize for maintainability, readability, extensibility (+ tests + docs)

Target layout (move-only commits first, then behavior changes):

```
wsgi.py / src/app_factory.py / src/extensions.py
src/blueprints/     pages, auth, chat, ai, profile, contacts, billing, admin, tasks
src/services/       auth, session, conversation, user, ai_model, contact, billing, storage,
                    transcription, proactive, relationship, mailer
src/services/integrations/   email_service, calendar_service   (moved from components/)
src/providers/      base (LLMProvider protocol), openai, anthropic, gemini, registry
src/ai/             agent (hand-rolled tool loop), tools, memory (episodic), short_term, voice
src/models/         existing + new tables
```

~38 routes map to blueprints per the verified route map. Delete dead weight: `src/prototypes/`, `src/deprecated/`, `speech_to_text.py`, `text_to_speech.py`, `calendar_utilities.py`, `ms_voice.py`, `audio_record.py`, `google_service.py`, `create_app.py`, `db_create.py`, `AI_model_client.py`; `app.py` deleted at phase end.

**Tests (first-class this time):** `conftest.py` app-factory fixture (in-memory SQLite) + `client`/`login` helpers; regression tests for every BUG-x fix; service-layer unit tests; blueprint smoke tests; provider adapters tested with mocked SDK clients; tool-loop termination/dispatch tests; CI via GitHub Actions (pytest + ruff).

**Docs:** module docstrings; `docs/architecture.md` (request flow, service map, how to add a route/tool/provider); refreshed `README.md` (setup, env vars, run, test); `docs/INDEX.md` kept current.

## Phase 3 — Modernize the AI core (docs-first, hand-rolled)

**Before writing any adapter:** read current provider docs — claude-api skill for Anthropic; WebFetch official OpenAI + google-genai docs (these APIs churn; verify param names, tool-call formats, streaming APIs at implementation time).

- **3.1 Model registry in `config.py`:** premium → `claude-opus-4-8`, default → `claude-sonnet-4-6`, utility/summaries → `claude-haiku-4-5` (**no Fable**), + current OpenAI/Gemini equivalents. Replaces retired/invalid hardcoded IDs. `calculate_cost` fail-soft.
- **3.2 `LLMProvider` protocol** — `generate(model, system, messages, tools, max_tokens, stream) -> LLMResult(text, tool_calls, usage, stop_reason)`; thin adapters per provider; context as structured blocks, never string-concat. Known Anthropic constraints: no `temperature/top_p/top_k` on Opus 4.8 (400), `thinking={"type":"adaptive"}`, stream large max_tokens, handle `refusal`.
- **3.3 Hand-rolled native tool-use loop (`src/ai/agent.py`)** — replaces the entire `context_analyzer` cascade (deprecated `functions=` API, 4–5 sequential LLM hops). One loop on the persona model: generate → dispatch `tool_use` (`calendar_read/create`, `email_read/send`, `memory_search`, `schedule_checkin`) with ownership checks → feed `tool_result` back → until `end_turn` (max 6 iters). **No managed agent SDKs/frameworks** — plain loop we control.
- **3.4 pgvector replaces Pinecone** (zero extra infra once Postgres lands; embeddings start fresh). Remove the `save.txt` debug write.
- **3.5 Short-term memory out of the session cookie** → DB `ConversationState` per (user, ai).
- **3.6 De-block the chat turn:** app-owned `ThreadPoolExecutor` for TTS + memory writes (tasks re-enter `app.app_context()`, take primitives); no Celery/Redis.

## Phase 4 — Companion features

### 4.1 Episodic memory (adapted subset of the research design)
Replace "LLM summary → Pinecone top-k" with an **episode store** per (user_id, ai_id) in pgvector:
- `episode` table: `situation` (what happened, in context — the retrieval surface), `emotional_tone`, `key_insight` (the design's `surprise` — what mattered/was learned about the user), `importance` (0–1), `entity_tags` (people/places/events), `created_at`/`last_accessed`/`access_count`, `embedding` (`text-embedding-3-small`, 1536-dim — cheaper than 3-large, adequate at this scale).
- **Write path:** at conversation lulls/session end (reuses the existing summarize cadence), an Haiku-tier retrospective extracts episodes + structured `key_fact` rows (the design's consolidation step → our commitments/birthdays/deadlines).
- **Retrieval:** composite scoring per the design — `0.6·similarity + 0.15·recency(30d half-life) + 0.10·reinforcement(log, capped) + 0.15·importance`, with access write-back. The companion naturally "remembers what matters, forgets trivia."
- **MVP skips:** priming table, candidate-lessons pipeline, pruning job (add pruning later; config constants kept tunable).
- Exposed to the agent as the `memory_search` tool + injected relationship context.

### 4.2 Voice
- **TTS → Gemini `gemini-3.1-flash-tts-preview`** behind a small `TTSProvider` interface, using audio tags for emotional expressivity matched to the companion's tone; **OpenAI TTS fallback** (it's a preview model). Verify exact API shape from Google docs at implementation time.
- **STT (new):** wire the dead mic button (`chat.html:176`) → browser `MediaRecorder` → `POST /transcribe` (`gpt-4o-transcribe`; verify current docs) → text lands in the textarea for review-before-send; `/send_message` unchanged.

### 4.3 Agent-scheduled proactive outreach (redesigned per feedback)
The **LLM does the scheduling**, not fixed cron kinds. New `scheduled_message` table (user_id, ai_id, `scheduled_for`, `trigger_context`, `status`). Three ways messages get scheduled:
1. **Default daily check-in** at a user-set time (the baseline experience, opt-in at onboarding).
2. **In-chat commitment detection:** user says "I'll sleep by 11pm tonight!" → agent calls `schedule_checkin` tool → morning follow-up ("how'd it go?"). Same for detected events ("interview Thursday 4pm" → good-luck message ~1h before).
3. **Nightly planning pass** (only for users opted into the calendar experiment): per user, an LLM call reviews tomorrow's calendar + due `key_fact`s and schedules 0–2 contextual messages (encouragement, prep nudges) — like a friend who knows your week.

**Delivery:** platform cron hits authenticated `POST /tasks/proactive-tick` every ~15 min; due messages get their content generated **at delivery time** (fresh context, persona voice, SKIP gate — model can decide not to send). **Anti-spam invariants:** hard cap 1–2 proactive messages/day, quiet hours, consent required (`consent_granted_at`), one-tap "less often / pause," no dark patterns. Delivery = in-app `Message(initiated=True)` + unread badge; email later (backlog).

### 4.4 Relationship model
`relationship_state` (first_met_at, streaks, total_interactions, tone_prefs) + `key_fact` (structured, filterable — vector search can't answer "what's due tomorrow"). `RelationshipService.context_block()` injected into the system prompt ("day 12 together; prefers gentle nudges; upcoming: interview Thursday"). Surfaced subtly: "day N together" header line + editable "what I remember" view. No streak-guilt mechanics.

### 4.5 UI redesign (new deliverable)
Using the **frontend-design skill**, produce `docs/designs/design.md`: brand identity for "a companion that actually acts" — color palette, typography, visual style, motion/tone principles, component direction — explicitly avoiding generic AI-slop aesthetics. Plus a **ready-to-run build prompt** for a Claude design session to implement the new UI (chat, onboarding, homepage, settings). Homepage hero *shows* a proactive message; onboarding gains a "let your companion into your world" step (Google connect + consent + check-in time). Deferred items (IP roster, "uncensored" bullet at `pricing.html:176`) stay untouched, flagged as launch blockers.

**Phase-4 MVP order:** STT (independent, ships after Phase 1) → episodic memory + key_facts → scheduled_message infra + daily check-in → commitment check-ins + calendar experiment → Gemini TTS swap → design.md + UI build prompt.

---

## Multi-session context management (this will span sessions)

- Copy this plan to `docs/designs/` as the executable roadmap; update `project.md` with the locked decisions; rewrite `.context/backlog.md` (close absorbed items, add deferred prod-hardening items); record BOOT-2/BOOT-3 decisions in the bootstrap sprint and flip it active.
- Sprint files per phase (`stabilize`, `modularize`, `modernize-ai`, `reposition`) with task notepads; checkpoint `.context/checkpoints/current.md` at every phase transition and ~30 min (the repo's hooks already enforce this).
- Add a `CLAUDE.local.md` quick-orientation note (current phase, where the plan lives, what's next) so a fresh/compacted session re-orients in one read.
- Save maintainer preferences to persistent memory (no Fable subagents/models — cost; docs-first for provider APIs; hand-rolled over managed frameworks; tests+docs are first-class; user learned to code on this project).

## Git strategy

History rewrite on `master` first → then branch per phase; one commit per backlog item (ID in message); move-only commits separate from behavior changes; merge + tag per phase.

## Verification

Per-phase: full pytest suite green; boot the app locally (`ProductionConfig` semantics, DEBUG off) and run one real chat turn; Phase 3 — a chat turn exercising each tool via the new loop; Phase 4 — force a proactive tick end-to-end (schedule → tick → in-app message), record + transcribe a message, verify episodic recall of a prior conversation fact. CI (pytest + ruff) from Phase 2.

## Key risks

1. Fresh Alembic baseline must come after ALL model edits (incl. Phase-4 tables).
2. Provider APIs drift — docs-first rule before each adapter; Opus 4.8 rejects legacy sampling params with 400s.
3. Background threads need `app.app_context()` + primitives, not request-bound ORM objects.
4. `gemini-3.1-flash-tts-preview` is a preview model — keep the OpenAI fallback wired.
5. Proactive outreach must fail quiet (SKIP gate + caps) — a buggy tick that spams is the worst possible first impression.
6. Launch blockers (deliberately deferred): IP character roster, "uncensored" tier, CSRF/hardening, deploy target.
