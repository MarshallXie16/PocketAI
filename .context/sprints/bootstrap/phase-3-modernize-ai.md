# Task Notepad — Phase 3: Modernize AI Core

**Ticket:** task #5 · **Branch:** `phase-3-modernize-ai` · **Started:** 2026-07-01
**Scope (roadmap §Phase 3):** docs-first provider adapters (NO Fable); hand-rolled native tool-use loop replacing context_analyzer; memory off Pinecone; short-term memory out of session cookie; de-blocked chat turn. Prereq: `.context/research/provider-apis-2026-07.md` (research agent, in flight).

## Design (orchestrator, pre-implementation)

**Module layout**
- `src/providers/base.py` — `ToolCall(id,name,args)`, `Usage(input,output)`, `LLMResult(text, tool_calls, usage, stop_reason, raw)`, `LLMProvider` protocol: `generate(*, model, system, messages, tools=None, max_tokens=..., stream=False) -> LLMResult`. `stop_reason ∈ {end_turn, tool_use, max_tokens, refusal, error}` (normalized).
- `src/providers/anthropic_provider.py`, `openai_provider.py`, `gemini_provider.py` (google-genai SDK), `registry.py` (model_id → provider via config MODEL_REGISTRY; `calculate_cost` fail-soft lives here).
- `src/ai/agent.py` — the loop: build system prompt (persona + mode + hidden prompt + system info [+ relationship block in Phase 4]) → generate → dispatch tool_use (ownership enforced per-tool via user_id) → feed tool_result → until end_turn / max 6 iterations / refusal. Hand-rolled, no SDK agent runners.
- `src/ai/tools.py` — declarations + dispatch: calendar_read, calendar_create, email_read, email_send, memory_search (+ schedule_checkin in Phase 4b). Wraps services/integrations.
- `src/ai/memory.py` — `MemoryStore`: SQLAlchemy `memory_entry` table, embedding as float32 BLOB, brute-force cosine ranking in Python. Replaces Pinecone.
- `src/ai/short_term.py` — `ConversationState` model (user_id, ai_id unique pair; memory_queue JSON, memory_queue_count, past_context) + helpers. Replaces session-cookie queue.
- `src/ai/background.py` — module ThreadPoolExecutor(4); `submit(app, fn, *args)` re-enters app_context; used for TTS + memory writes.
- `conversation_service.run_ai_response` rewired to agent.py; keep the `src.blueprints.chat.run_ai_response` patch seam (tests rely on it).
- DELETE: `src/components/context_analyzer.py`, `ai_models.py`, `memory.py`, `src/utils/AI_model_client.py` + their tests + ruff ignores. `voice_handler.py` → `src/ai/voice.py` (Phase 4c replaces internals).

## Decisions
**Decision:** Vector memory = SQLAlchemy table + float32-BLOB embeddings + in-Python cosine, NOT pgvector (yet).
**Tier:** 2. **Rationale:** roadmap assumed managed Postgres from Phase 1, but the maintainer deferred deployment — dev runs SQLite, and pgvector doesn't exist there. Per-(user,ai) episode counts are small (hundreds–thousands); brute-force cosine is milliseconds. The store interface hides ranking, so pgvector becomes a drop-in index optimization when Postgres lands (added to backlog LAUNCH-3 note). **Alternatives rejected:** keep Pinecone (paid infra, maintainer wants off), local Chroma (ephemeral-FS problem returns at deploy), dev-Postgres-via-Docker (infra user didn't ask for). **Reversibility:** store interface unchanged. **Scope:** src/ai/memory.py, models.

**Decision:** Model tiers (config MODEL_REGISTRY): default `claude-sonnet-4-6`, premium `claude-opus-4-8`, utility/summaries `claude-haiku-4-5`; keep OpenAI + Gemini adapters for user-selectable models. NO Fable (maintainer: cost).
**Tier:** 2 (maintainer pre-approved tiers in plan review).

## Reviews (1 native opus + 1 external codex gpt-5.5)
Codex verified all adapter wire-shapes against the INSTALLED SDK source: clean. Findings fixed:
- **[codex Critical] Consequential tools executed on model say-so** → server-side two-phase gate: `calendar_create`/`email_send` store a draft in `ConversationState.pending_action`; `confirm_action` executes only if a genuine USER message exists with id > draft's message_id (injection in the same turn cannot confirm itself). Tests in `test_tool_confirmation.py`.
- **[native C1] Memory queue reset before background success = silent loss** → queue persists; `consolidate_and_save` removes exactly the consumed lines after success/gate-drop; failures leave the queue for retry next turn.
- **[native M1] email contact lookup dead NoResultFound branch** (`get_user_contact` returns None) + `search_inbox` session-scoped user_id → fixed, user_id threaded from dispatch.
- **[native M2] tool schemas demanded RFC3339 offsets the model was never given** → `get_system_info` now includes the numeric UTC offset.
- **[native M3] persona `.format()` crashed on user braces** (pre-existing, carried over) → token `.replace()`.
- **[codex M] ConversationState get_or_create race** → with_for_update + IntegrityError retry; queue updates documented last-write-wins.
- **[codex M/native m2] past_context never wired** → `AgentTurn.tool_context` collected in the loop, stored (truncated 2000 chars), passed as `extra_context` next turn.
- Minors: generic tool error strings (no internals leak), Gemini text-parts read (response.text raises on tool-only candidates), embedding-dim guard self-consistent vs query embedding, regenerate trailing-user-row replaced not duplicated.

## Verification
130 tests green (zero env keys), ruff clean, app boots, chat smoke OK. NOT yet verified with real API keys — needs a live chat turn + tool round-trip when maintainer runs with a populated .env.

## For Phase 4 / docs
- docs/architecture.md still describes src/components/ as "legacy, to be replaced" — update in the Phase-4 docs pass (components/ is now gone).
- 'gpt-5-mini' and 'gemini-3-pro-preview' pricing in MODEL_REGISTRY flagged unverified (cost logging only).
- Research agent claimed "Sonnet 5 supersedes 4.6" without web access — NOT adopted; env-confirmed lineup (Opus 4.8/Sonnet 4.6/Haiku 4.5) used.

## Status: COMPLETE (2026-07-01) — merged to master
