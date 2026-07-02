# Architecture

**Phase 4 (companion features) — current state as of branch `phase-4-companion`.**

---

## Request flow

```
Browser
  │
  ▼
Blueprint (src/blueprints/<domain>.py)
  │   Validates auth (flask-login), parses request, delegates to a service.
  │   Never touches the DB directly. Never contains business logic.
  ▼
Service (src/services/<name>_service.py)
  │   Owns business logic, DB commits, and external calls.
  │   Returns plain Python values or raises exceptions for the blueprint to handle.
  ├──► SQLAlchemy model (src/models/) — persistent state
  ├──► Integration (src/services/integrations/) — Google Calendar / Gmail
  └──► AI core (src/ai/) — agent loop, memory, voice, prompts
  ▼
Response
  Blueprint renders a template or returns JSON.
```

### AI chat turn (detailed)

```
chat_bp.send_message
  │
  ▼
conversation_service.run_ai_response()
  │   Load history (Message rows) + ConversationState (short-term context)
  │   Inject relationship_block (RelationshipState, KeyFacts, tone prefs)
  ▼
agent.run_turn()                         ← src/ai/agent.py
  │   resolve_model → get_provider (registry)
  │   build_system_prompt (persona + mode + humanize + system_info + rel. block)
  │   Loop (max 6 iterations):
  │     provider.generate(model, system, messages, tools)
  │     if stop_reason == tool_use:
  │       tool_registry.dispatch(call.name, call.args, user_id, ai_id)
  │       append assistant blocks + tool_result → continue
  │     else: break
  ▼
Provider adapter (src/providers/)        ← LLMProvider protocol
  │   AnthropicProvider | OpenAIProvider | GeminiProvider
  │   Normalizes SDK response → LLMResult(text, tool_calls, stop_reason, usage)
  ▼
Tools (src/ai/tools.py)
  │   memory_search → src/ai/memory.search_memory()
  │   calendar_read / calendar_create (draft) → GoogleCalendar
  │   email_read / email_send (draft) → Gmail
  │   schedule_checkin → proactive_service.schedule_checkin()
  │   confirm_action → executes the stored draft (gate enforced)
  ▼
conversation_service (post-turn)
  │   relationship_service.record_interaction() — streak/counter bump
  │   Append to ConversationState.memory_queue
  │   If queue >= chunk_size: background.submit(memory.consolidate_and_save)
  ▼
chat_bp: generate voice (VoiceHandler) if enabled → return JSON
```

---

## Confirmation gate for consequential tools

`calendar_create` and `email_send` are *consequential* — they write to the
outside world. They follow a two-step draft/confirm pattern enforced
server-side:

1. **Draft.** The tool stores `{tool, args, message_id}` in
   `ConversationState.pending_action`, where `message_id` is the latest
   `Message.id` at draft time. The tool output instructs the model to show
   the draft to the user and wait.

2. **Confirm.** When the model calls `confirm_action`, the handler checks that
   a genuine user `Message` (sender=`'user'`) exists with `id >
   pending_action.message_id`. Only then is the action executed.

**Security property:** hostile content inside an email or calendar event the
companion just read cannot draft and auto-confirm within the same turn,
because no new user message exists yet. Content injection cannot clear its own
gate.

---

## Episodic memory

### Write path (background, off the hot path)

After every `memory_chunk_size` message pairs (default 6), `memory.consolidate_and_save()` runs on the background thread pool (`src/ai/background.py`, 4-worker `ThreadPoolExecutor`):

1. **Retrospective extraction** — send the queued exchange lines to `UTILITY_MODEL` (`claude-haiku-4-5`) with a structured prompt. The model returns JSON: `{important, situation, emotional_tone, key_insight, importance, entity_tags, key_facts[], tone_note}`.

2. **Episode write** — if `important == true`, a `MemoryEntry` row is written with `content`, float32 embedding (via `text-embedding-3-small`), and episodic fields.

3. **Key facts** — up to 5 `KeyFact` rows (type: `commitment|event|person|preference|goal`) are extracted. Time-bound facts carry `due_at` and drive proactive follow-through.

4. **Tone note** — if the model surfaces a style observation, it is appended to `RelationshipState.tone_prefs` (capped at 10).

5. **Queue drain** — only the successfully-consumed lines are removed. A background failure leaves the queue intact; the next turn retries.

### Read path (`memory_search` tool)

`memory.search_memory(user_id, ai_id, query, top_k=3)` returns the top-k matching memories using **composite recall scoring**:

```
score = similarity × 0.60
      + recency    × 0.15    # exponential decay, ~30-day half-life
      + reinforce  × 0.10    # log-scaled access count
      + importance × 0.15    # set at write time (0.0–1.0)
```

Similarity is in-process cosine similarity over float32 blobs stored in `MemoryEntry.embedding`. Ranked rows have `last_accessed` bumped and `access_count` incremented (reinforcement). Swap for pgvector when a managed Postgres exists — the scoring stays unchanged.

---

## Proactive outreach flow

### Scheduling sources (three)

| Source | Mechanism |
|--------|-----------|
| **Daily check-in** | `proactive_service._materialize_daily_checkin()` — creates a `ScheduledMessage(trigger='daily_checkin')` once per local calendar day if the user has set `UserSettings.daily_checkin_time` |
| **In-chat agent** | `schedule_checkin` tool — the companion calls this during a conversation when the user makes a commitment or mentions an upcoming event. Stored via `proactive_service.schedule_checkin()` |
| **Nightly planner** | `proactive_service._run_planner_if_due()` — for `calendar_experiment` opt-ins, runs at most ~once per day: reads the next 24h of calendar + unresolved `KeyFact` rows, asks `UTILITY_MODEL` to propose 0–2 contextual check-in moments |

### Tick endpoint

`POST /tasks/proactive-tick` (defined in `src/blueprints/tasks.py`) is hit by an external cron **every ~15 minutes**. It is completely disabled when `PROACTIVE_TICK_SECRET` is unset. Authentication: `hmac.compare_digest` of the `X-Tick-Secret` request header against the env var.

Each tick:
1. **Materializes** any due daily check-ins.
2. **Runs the planner** (if due) for `calendar_experiment` users.
3. **Delivers** all `ScheduledMessage` rows with `status='pending'` and `scheduled_for <= now`, in schedule order (batch cap: 50/tick).

### Delivery guardrails (server-side, not prompt-enforced)

For each due row, delivery is suppressed if:
- User has no `proactive_consent_at` (explicit opt-in required)
- Current time falls within `UserSettings.quiet_hours_start`..`quiet_hours_end`
- `sent_today` count >= `UserSettings.max_proactive_per_day` (default 2)

### SKIP gate

Content is **generated at delivery time** (not pre-written). The companion model receives the initiate prompt with `trigger_context` and may reply `SKIP` if reaching out adds no real value. Only a non-SKIP reply is saved as `Message(initiated=True)` and delivered.

---

## Directory map

### `src/blueprints/`

One file per domain. Each file creates a `Blueprint`, defines routes, and delegates everything else to a service. Route paths are frozen — changing them requires updating frontend fetch calls and links.

| File | Routes |
|------|--------|
| `pages.py` | `/`, `/pricing`, `/legal/*`, error pages |
| `auth.py` | `/login`, `/signup`, `/logout`, Google OAuth callback |
| `chat.py` | `/chat`, `/send_message`, `/regenerate`, `/edit_message`, `/load_messages`, `/transcribe` |
| `ai.py` | `/ai-onboarding`, `/ai-settings/<id>`, `/change-ai/<id>`, `/profile/delete-ai/<id>` |
| `profile.py` | `/profile`, `/profile/settings`, `/onboarding` |
| `contacts.py` | `/contacts/*` |
| `billing.py` | `/checkout`, `/webhook`, `/cancel` |
| `admin.py` | `/admin/reset_credits` |
| `tasks.py` | `/tasks/proactive-tick` (cron endpoint, no user session) |

### `src/providers/`

Provider-agnostic LLM interface (Phase 3). All model calls go through the `LLMProvider` protocol; adapters normalize SDK-specific shapes into `LLMResult`.

| File | Purpose |
|------|---------|
| `base.py` | `LLMProvider` protocol, `LLMResult`, `ToolCall`, `Usage`, normalized stop-reason constants |
| `anthropic_provider.py` | Anthropic Messages API adapter; streams above 8 k tokens; adaptive thinking on Opus 4.8; never sends `temperature`/`top_p` (400 on Opus 4.8) |
| `openai_provider.py` | OpenAI Responses API adapter; `json.loads` on tool-call arguments; no `temperature`/`top_p` on GPT-5 series |
| `gemini_provider.py` | Google `google-genai` client adapter; synthesizes tool-call ids (Gemini has none natively) |
| `registry.py` | `resolve_model()` (alias → canonical id), `get_provider()` (cached adapter), `calculate_cost()` (fail-soft cost logging) |

Model registry and aliases live in `config.py` (`MODEL_REGISTRY`, `MODEL_ALIASES`, `DEFAULT_MODEL`, `UTILITY_MODEL`).

### `src/ai/`

Hand-rolled agent loop and companion intelligence (Phase 3).

| File | Purpose |
|------|---------|
| `agent.py` | `run_turn()` — the agent loop: generate → dispatch tools → feed results → repeat; caps at `MAX_TOOL_ITERATIONS=6` |
| `tools.py` | Tool declarations (`TOOLS` list, Anthropic `input_schema` format as the neutral house format), `dispatch()`, draft/confirm logic for `CONSEQUENTIAL_TOOLS` |
| `memory.py` | `save_memory()`, `search_memory()` (composite recall scoring), `consolidate_and_save()` (retrospective extraction + key-fact writes) |
| `background.py` | 4-worker `ThreadPoolExecutor`; `submit(app, fn, ...)` runs tasks inside `app.app_context()` |
| `voice.py` | `VoiceHandler` — routes to `GeminiVoice` (primary, `gemini-3.1-flash-tts-preview`) or `OpenAIVoice` (fallback); uploads to S3 |
| `prompts.py` | `build_system_prompt()` — assembles persona + conversation-mode + humanize + system_info + relationship block |

### `src/services/`

Business logic layer. Services own DB commits; blueprints do not call `db.session.commit()` directly.

| File | Purpose |
|------|---------|
| `auth_service.py` | Local login/session bootstrap; Google OAuth token exchange and refresh |
| `session_service.py` | Per-session AI state: active AI, memory queue, conversation mode |
| `conversation_service.py` | Chat turn orchestration: history load → agent loop → memory queue → background consolidation |
| `relationship_service.py` | Streak/counter bumps after each turn; `context_block()` renders relationship + key-fact context for the system prompt |
| `proactive_service.py` | Scheduling (daily check-in, in-chat, planner), tick delivery with consent/quiet-hours/cap guardrails, SKIP gate |
| `transcription_service.py` | STT via `gpt-4o-transcribe`; used by `POST /transcribe` |
| `ai_model_service.py` | AI model CRUD; `get_owned_ai()` is the ownership/security gate for all AI routes |
| `user_service.py` | User settings persistence |
| `contact_service.py` | Contact list CRUD |
| `billing_service.py` | Stripe fulfillment (webhook path; no logged-in session, user from `client_reference_id`) |
| `storage_service.py` | S3-backed profile image and voice file upload/delete |

### `src/services/integrations/`

Google API adapters. Used directly by `src/ai/tools.py`; not called from blueprints.

| File | Purpose |
|------|---------|
| `calendar_service.py` | Google Calendar read/create via service account credentials |
| `email_service.py` | Gmail read/send; contact matching |

### `src/models/`

SQLAlchemy model definitions. One file per table group.

| File | Tables |
|------|--------|
| `users.py` | `User`, `UserSettings`, `AIModel`, `Contacts` |
| `google_user.py` | `GoogleUser` (OAuth tokens, stored Fernet-encrypted) |
| `message.py` | `Message` (conversation history; `initiated=True` for proactive messages) |
| `billing.py` | `StripeEvent` (idempotency ledger for webhook fulfillment) |
| `conversation_state.py` | `ConversationState` — short-term memory queue, past tool context, pending action draft |
| `memory_entry.py` | `MemoryEntry` — episodic memory rows with float32 embeddings and scoring fields |
| `relationship.py` | `RelationshipState`, `KeyFact`, `ScheduledMessage` |

### `src/utils/`

Cross-cutting helpers with no business logic.

| File | Purpose |
|------|---------|
| `crypto.py` | `EncryptedString` TypeDecorator (Fernet); `TOKEN_ENCRYPTION_KEY` from env |
| `forms.py` | Flask-WTF form definitions |
| `utils.py` | Date utilities, `calculate_cost()`, miscellaneous helpers |
| `AI_model_client.py` | Lazy client singletons (OpenAI, Anthropic, Gemini); conditional on env keys |

---

## App factory pattern

`src/app_factory.py:create_app()` is the single entry point for building the Flask app. Nothing runs at import time.

- `wsgi.py` calls `create_app()` after `load_dotenv()`, so API keys and secrets are in the environment before any config or extension initializes.
- Tests pass a config class directly: `create_app(TestingConfig)` → in-memory SQLite, no real credentials needed.
- `root_path` is pinned to the repo root (`BASE_DIR`) so that `src/templates/` and `src/static/` resolve correctly even though `app_factory.py` lives one level deeper in `src/`. Without this pin, Flask would look for templates relative to `src/`.
- The Google OAuth client is registered idempotently (safe for repeated `create_app()` calls in tests).

---

## Conventions

**Route paths never change without frontend updates.** Blueprint endpoint names are namespaced (e.g. `auth.login`) but URL paths are identical to the monolith. Any path change requires auditing `url_for()` calls in templates and `fetch()` calls in `.js` files.

**Services own business logic and DB commits.** A blueprint hands off to a service and handles the result. If a service raises, the blueprint catches and returns the appropriate HTTP response or flash message. `db.session.commit()` belongs in the service, never in a route handler.

**Blueprints stay thin.** Auth checks (`@login_required`, ownership via `get_owned_ai()`), request parsing, response formatting. That is all.

**Ownership is enforced at the service boundary.** `ai_model_service.get_owned_ai(current_user, ai_id)` returns 404 if the AI does not belong to the requesting user. Every route that accepts an AI id from the URL or request body must pass through this function.

**Tools fail soft.** A tool error returns an error string to the model (never raises to the agent loop). The model apologizes and suggests retrying; the request never 500s from a tool failure.

---

## How-to recipes

### Add a route

1. Choose the right blueprint file in `src/blueprints/`.
2. Define the route function. Keep it thin: parse args, call a service, return a response.
3. If the route mutates state, put the mutation in a service function.
4. Add a test in `src/tests/` that hits the route via the test client.

### Add a service

1. Create `src/services/<name>_service.py`.
2. Import the service in the relevant blueprint(s). Do not import blueprints from services (circular).
3. The service may import models and extensions (`db`), but not request-bound objects (`current_user`, `request`). Pass those as arguments from the blueprint.

### Add a model

1. Add the class to the appropriate file in `src/models/`.
2. Import the model in `src/app_factory.py` (or anywhere that runs before `db.create_all()`) so SQLAlchemy registers it.
3. During development, `db.create_all()` (via the Flask shell) adds new tables. **Do not generate a new Alembic migration yet** — a clean baseline migration will be generated once all Phase-4 tables are finalized (LAUNCH-5). Running `flask db migrate` against the current drifted history will produce incorrect diffs.

### Add a tool

1. Add a declaration to the `TOOLS` list in `src/ai/tools.py`. Use Anthropic's `input_schema` format (JSON Schema object with `type`, `properties`, `required`) — the provider adapters translate this to OpenAI/Gemini wire format.
2. Add a dispatch branch in `tools.dispatch()`. Return a string result (or error string — never raise).
3. If the tool writes to the outside world, add its name to `CONSEQUENTIAL_TOOLS`. It will automatically go through the draft/confirm gate.
4. Add a test in `src/tests/`.

### Add a provider

1. Create `src/providers/<name>_provider.py` implementing the `LLMProvider` protocol from `src/providers/base.py`. The adapter must normalize its SDK's response into `LLMResult` (text, tool_calls with `id`/`name`/`args`, stop_reason using the `STOP_*` constants, usage).
2. Register the provider name in `src/providers/registry.get_provider()`.
3. Add at least one model id that routes to this provider in `config.py MODEL_REGISTRY` (see next recipe).

### Add a model id

1. Add an entry to `config.py MODEL_REGISTRY`:
   ```python
   'provider-model-id': {
       'provider': '<provider_name>',
       'input': <price_per_mtok_usd>,
       'output': <price_per_mtok_usd>,
       'label': 'Display Name',
   }
   ```
2. If the model replaces a stored legacy name, add the old name → new id mapping to `MODEL_ALIASES`.
3. For old rows in the database that carry the legacy name, `resolve_model()` will handle the alias transparently at runtime.

### Where tests go

All tests live in `src/tests/`. The `conftest.py` fixture provides:
- `app` — a `TestingConfig` app (in-memory SQLite, CSRF disabled)
- `client` — a Flask test client
- `login` — a helper that creates and logs in a test user

Test files are named `test_<domain>.py`. Service-layer unit tests mock external calls (LLM providers, Google APIs, S3). Blueprint smoke tests use the test client and assert status codes and response content.

---

## Known debt

The following items are tracked in `.context/backlog.md`:

- **LAUNCH-1** — CSRF protection is not yet wired (Flask-WTF `CSRFProtect` + token injection in templates and `fetch()` calls).
- **LAUNCH-2** — Cookie/transport hardening (`ProxyFix`, Talisman, rate limiting) pending deploy target decision.
- **LAUNCH-3** — No deploy target chosen; `Procfile` (Heroku) and `.ebextensions/` (Elastic Beanstalk) are both present and conflicting.
- **LAUNCH-4** — IP character roster + "uncensored" tier must be resolved before public launch.
- **LAUNCH-5** — Alembic baseline migration pending completion of Phase-4 schema changes.
