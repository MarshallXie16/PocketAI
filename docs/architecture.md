# Architecture

**Phase 2 (modularize) — current state as of branch `phase-2-modularize`.**

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
  └──► Component (src/components/) — legacy AI core (context analyzer, memory, LLM calls)
  ▼
Response
  Blueprint renders a template or returns JSON.
```

The AI chat turn is the most complex path: `chat_bp` → `conversation_service.run_ai_response()` → `context_analyzer` (tool routing) → one or more LLM calls → `memory` (Pinecone) → reply saved and returned. This whole flow is replaced by the hand-rolled tool loop in Phase 3.

---

## Directory map

### `src/blueprints/`

One file per domain. Each file creates a `Blueprint`, defines routes, and delegates everything else to a service. Route paths are frozen — changing them requires updating frontend fetch calls and links.

| File | Routes |
|------|--------|
| `pages.py` | `/`, `/pricing`, `/legal/*`, error pages |
| `auth.py` | `/login`, `/signup`, `/logout`, Google OAuth callback |
| `chat.py` | `/chat`, `/send_message`, `/regenerate`, `/edit_message`, `/load_messages` |
| `ai.py` | `/ai-onboarding`, `/ai-settings/<id>`, `/change-ai/<id>`, `/profile/delete-ai/<id>` |
| `profile.py` | `/profile`, `/profile/settings`, `/onboarding` |
| `contacts.py` | `/contacts/*` |
| `billing.py` | `/checkout`, `/webhook`, `/cancel` |
| `admin.py` | `/admin/reset_credits` |

### `src/services/`

Business logic layer. Services own DB commits; blueprints do not call `db.session.commit()` directly.

| File | Purpose |
|------|---------|
| `auth_service.py` | Local login/session bootstrap; Google OAuth token exchange and refresh |
| `session_service.py` | Per-session AI state: active AI, memory queue, conversation mode |
| `conversation_service.py` | Chat turn orchestration: history load → context analyzer → LLM call → memory flush |
| `ai_model_service.py` | AI model CRUD; `get_owned_ai()` is the ownership/security gate for all AI routes |
| `user_service.py` | User settings persistence |
| `contact_service.py` | Contact list CRUD |
| `billing_service.py` | Stripe fulfillment (webhook path; no logged-in session, user from `client_reference_id`) |
| `storage_service.py` | S3-backed profile image and voice file upload/delete |

### `src/services/integrations/`

Google API adapters moved from `src/components/` in Phase 2. These are not yet rewritten — they retain their original structure and will be modernized in Phase 3 alongside the tool loop.

| File | Purpose |
|------|---------|
| `calendar_service.py` | Google Calendar read/create via service account credentials |
| `email_service.py` | Gmail read/send; contact matching |

### `src/components/` — legacy AI core (replaced in Phase 3)

These modules implement the original agentic loop and will be deleted when Phase 3 lands `src/providers/` and `src/ai/`.

| File | Purpose |
|------|---------|
| `ai_models.py` | Persona prompt assembly; multi-provider LLM dispatch (stale model IDs) |
| `context_analyzer.py` | Intent classifier: deprecated `functions=` API → tool routing |
| `memory.py` | Long-term memory: OpenAI embeddings → Pinecone upsert/search |
| `voice_handler.py` | TTS via OpenAI (write path only; STT was never completed) |

### `src/models/`

SQLAlchemy model definitions. One file per table group.

| File | Tables |
|------|--------|
| `users.py` | `User`, `UserSettings`, `AIModel`, `Contacts` |
| `google_user.py` | `GoogleUser` (OAuth tokens, stored Fernet-encrypted) |
| `message.py` | `Message` (conversation history) |
| `billing.py` | `StripeEvent` (idempotency ledger for webhook fulfillment) |

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

`src/components/` is deliberately not cleaned up — it will be replaced wholesale in Phase 3. Do not invest in fixing it.
