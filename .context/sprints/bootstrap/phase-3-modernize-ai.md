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

## Status: IN PROGRESS — awaiting provider-API research brief for adapter implementation; scaffolding (protocol, models, store, loop skeleton) can proceed
