# Project: PocketAI

**Last updated:** 2026-07-01
**Size cap:** ~200 lines

PocketAI is a Flask web app being repositioned as **"a companion that actually acts"** — a persistent, personalized AI presence that maintains a relationship with you (persona, episodic memory, voice) AND takes real action in your life (Google Calendar, Gmail, proactive check-ins). Identity locked by the maintainer 2026-07-01. **Roadmap: `docs/designs/overhaul-roadmap.md`** (supersedes the original assessment in `overhaul-and-repositioning.md`).

**Overhaul status (2026-07-02): COMPLETE.** Phases 0–4 all merged to master (secrets purged → bugs fixed → modularized → AI core modernized → companion features built). 177 tests green with zero API keys. Remaining work lives in `backlog.md`: LAUNCH-1..6 (pre-launch: CSRF, hardening, deploy target, IP-roster/uncensored decision, Alembic baseline, live-key verification), UI-1..4 (frontend integration, waiting on Cloud Design), DEBT-5..7. Proactive features are dormant until the consent UI ships (UI-3). **Not deployed; deployment deferred by maintainer.**

---

## Tech Stack

| Category | Technology | Notes |
|----------|-----------|-------|
| Language/Runtime | Python 3.11.9 | `runtime.txt` (Heroku pin) |
| Framework/Web | Flask (single `app.py` monolith, ~1600 lines) | No blueprints/service layer yet |
| Frontend | Jinja2 server-rendered templates + Tailwind (CDN) + Alpine.js | `src/templates/` |
| Auth | Flask-Login (email/password) + Authlib (Google OAuth) | Sessions in signed cookie |
| ORM / Migrations | Flask-SQLAlchemy + Flask-Migrate (Alembic) | ⚠️ migration history has drifted (see below) |
| Database | SQLite (dev, **committed to repo**), Postgres (prod intended) | `config.py` |
| Vector DB | **Pinecone** (active, index `user-pool`) | Chroma is imported but its class is commented out — dead |
| AI providers | OpenAI, Google Gemini, Anthropic Claude | Model IDs hardcoded & stale (see limitations) |
| Voice | OpenAI TTS (out) — **active**; STT (in) — **commented out / never shipped** | mic button in UI is non-functional |
| Integrations | Google Calendar API, Gmail API, Contacts | Routed via a hand-rolled LLM intent classifier |
| Payments | Stripe (subscriptions) | Webhook fulfillment is currently **broken** |
| Object storage | AWS S3 (`boto3`) — active | Azure storage libs are declared but unused |
| Testing | pytest | 4 test files in `src/tests/` |
| Deploy | Heroku (`Procfile`) **and** AWS Elastic Beanstalk (`.ebextensions/`) | Conflicting; neither is deploy-ready. Pick one. |

See `requirements.txt` (currently **fully unpinned**, with duplicates and desktop-only libs — cleanup pending).

---

## Directory Structure

```
PocketAI/
├── wsgi.py                      # entry point (gunicorn target + dev runner)
├── config.py                    # env-driven select_config() + product constants (credits, memory)
├── requirements.txt             # PINNED (requirements-dev.txt adds pytest/ruff)
├── pyproject.toml               # ruff + pytest config
├── .github/workflows/ci.yml    # CI: ruff + pytest
├── migrations/                  # stale — fresh Alembic baseline pending (LAUNCH-5); dev uses create_all
└── src/
    ├── app_factory.py           # create_app(): config, extensions, OAuth, blueprints, user loader
    ├── extensions.py             # db, migrate, login_manager, oauth singletons
    ├── blueprints/               # pages, auth, chat, ai, profile, contacts, billing, admin (thin routes)
    ├── services/                 # business logic: auth, session, conversation, ai_model, user,
    │   └── integrations/         #   contact, billing, storage + email/calendar (Google APIs)
    ├── components/               # LEGACY AI core (ai_models, context_analyzer, memory, voice_handler)
    │                             #   → replaced by src/providers/ + src/ai/ in Phase 3
    ├── models/                   # users (User/AIModel/AISettings/UserSettings/Contacts),
    │                             #   google_user (Fernet-encrypted tokens), message, billing (StripeEvent)
    ├── utils/                    # crypto (EncryptedString), forms (form_get), utils, AI_model_client (legacy)
    ├── templates/                # Jinja pages (UI redesign pending — Cloud Design)
    └── tests/                    # pytest suite: 34 green with zero env keys; live-API modules skipped
```

See `docs/architecture.md` for request flow and how-to-extend recipes.

---

## Architecture (post-Phase-2)

- **Factory + blueprints + services**: `create_app()` in `src/app_factory.py` (env-driven via `APP_ENV`; prod fails closed on missing secrets); 8 thin blueprints; business logic in `src/services/`. Route paths are frozen — the frontend JS hardcodes them.
- **Chat turn** (`conversation_service.run_ai_response` — still legacy internals, Phase-3 target): last N messages from SQL + rolling summary queue in the session cookie → `context_analyzer` LLM router (deprecated `functions=` API) → sequential tool calls → persona model → periodic summary into Pinecone. **Phase 3 replaces this** with a hand-rolled native tool-use loop on an `LLMProvider` protocol (Opus 4.8 / Sonnet 4.6 / Haiku 4.5 — NO Fable per maintainer), pgvector memory, DB-backed short-term state, ThreadPoolExecutor for TTS/memory writes.
- **Conventions**: services own DB commits; blueprints stay thin; every id-from-URL route goes through `ai_model_service.get_owned_ai()`; secrets only via env (`.env.example` documents them); tests must pass with zero API keys (mock at service boundary).

---

## How to Run

- **Dev server:** `./.venv/bin/python wsgi.py` (DevelopmentConfig → SQLite, DEBUG, 0.0.0.0:5000). Venv lives at `.venv/`.
- **DB bootstrap (dev):** `./.venv/bin/flask --app wsgi shell` → `db.create_all()` (Alembic baseline pending, LAUNCH-5).
- **Tests:** `./.venv/bin/pytest src/tests/ -q` — green with zero env keys. **Lint:** `./.venv/bin/ruff check .`. CI runs both.
- `.env` from `.env.example`; app boots keyless, AI/OAuth/Stripe features need real keys. See README.md for the full quickstart.

---

## Environment Variables

- **`DB_SECRET_KEY`** — Flask session secret (⚠️ falls back to a hardcoded default; must fail-closed in prod).
- **`DATABASE_URL`** — Postgres URL for prod (⚠️ `config.py` crashes at import if unset).
- **`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_APPLICATION_CREDENTIALS`** — Google OAuth + APIs.
- **`STRIPE_API_KEY`** + Stripe price lookup keys, `YOUR_DOMAIN` — billing.
- **AWS** creds + S3 bucket (referenced `app.py:68-73`); **OpenAI / Anthropic / Google GenAI / Pinecone** API keys.
- **`ADMIN_PASSWORD`** — gates `/admin/reset_credits` (⚠️ hardcoded default; endpoint is otherwise unprotected).

---

## Known Limitations & Gotchas (post-Phase-2)

- **Pre-launch blockers** (`backlog.md` LAUNCH-1..5): no CSRF; no rate-limiting/Talisman; no deploy target chosen (Heroku + EB artifacts both still present); IP character roster + "uncensored" pricing bullet + Gemini BLOCK_NONE safety settings deferred by maintainer decision; Alembic baseline pending (dev uses `create_all`).
- **Legacy AI core** (`src/components/` + `src/utils/AI_model_client.py`): stale/retired model IDs, deprecated `functions=` router, deprecated `google.generativeai` SDK, session-cookie short-term memory, serialized chat turn — all replaced in Phase 3.
- **Templates reference missing assets** (css/profile.css, js/profile.js, /upload_audio) — pre-existing; resolved by the UI redesign (Cloud Design, in flight).
- **Prebuilt roster rows were discarded** with the old DB — `/onboarding/ai/existing` has no templates to clone until re-seeded (`AIModel.is_template=True` rows; LAUNCH-4).

---

## Documentation

- **`docs/designs/overhaul-and-repositioning.md`** — full current-state assessment, phased overhaul→production plan, and the strategic repositioning brief. **Start here.**
- **`docs/INDEX.md`** — documentation index.
- **`.context/backlog.md`** — prioritized, actionable work items (security, bugs, tech debt, deploy, strategic spikes).
- **`.context/sprints/bootstrap/sprint.md`** — the first sprint (stabilize, secure, choose a direction).

---

## Source of Truth

This file is the authoritative project context; every session begins here. It reflects the codebase **as inherited** (pre-overhaul). Update it as the overhaul changes architecture, stack, or conventions so it never drifts.
