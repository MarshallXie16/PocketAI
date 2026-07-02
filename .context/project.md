# Project: PocketAI

**Last updated:** 2026-07-01
**Size cap:** ~200 lines

PocketAI is a Flask web app that gives each user one or more **personalized AI assistants** — custom persona + name + voice + conversation style — backed by **persistent long-term memory** (vector DB) and **real tool use** (Google Calendar, Gmail, contacts). It was built ~2022–2024, "agentic before AI agents were a category," was deployed on Heroku, and was taken down ~2 months ago (≈May 2026). It is being resurrected for a full overhaul (bug fixes, modularization, AI-core modernization) **and** a strategic repositioning toward the gap between task assistants (Claude/ChatGPT) and virtual companions (Character.ai). **See `docs/designs/overhaul-and-repositioning.md` — that is the north-star plan for this effort.**

> ⚠️ **This codebase is NOT production-ready and NOT currently secure.** Real user data and live OAuth tokens are committed to git; the app runs in DEBUG mode with a weak secret; several auth/billing endpoints are exploitable. Read the "Known Limitations" section and the overhaul doc before deploying anything. Fix the Phase-0 security items first.

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
├── app.py                       # THE MONOLITH: app factory + ~38 routes + all business logic + helpers
├── config.py                    # Dev/Testing/Production config classes
├── db_create.py                 # `db.create_all()` bootstrap (imports the whole monolith)
├── requirements.txt             # Unpinned deps (needs cleanup)
├── Procfile / runtime.txt / Aptfile / .slugignore   # Heroku artifacts
├── .ebextensions/ / .ebignore   # AWS Elastic Beanstalk artifacts (conflicts with Heroku)
├── migrations/                  # Alembic — DRIFTED from current models (see limitations)
├── save.txt                     # 34 KB debug dump written on every memory search — delete
└── src/
    ├── models/                  # SQLAlchemy: users, google_user, message
    ├── components/              # "Services": ai_models, memory, context_analyzer,
    │                            #   voice_handler(TTS), email_service, calendar_service,
    │                            #   speech_to_text(commented), text_to_speech(commented)
    ├── utils/                   # auth, extensions(db/migrate), utils, AI_model_client,
    │                            #   calendar_utilities(dead), ms_voice(dead), audio_record(dead),
    │                            #   google_service(empty), create_app(commented-out dead)
    ├── templates/               # 25 Jinja pages (chat, onboarding, pricing, settings, legal…)
    ├── tests/                   # pytest: date utils, context analyzer, calendar classify
    ├── prototypes/              # Experimental scripts + media (DALL·E/Vision/etc.) — dead weight
    ├── deprecated/              # Old desktop UI + another save.txt — dead weight
    ├── instance/users.db        # ⚠️ committed SQLite DB with REAL user data + OAuth tokens
    └── db/chroma.sqlite3        # ⚠️ committed Chroma vector store
```

---

## Architecture (current reality)

- **App factory** lives inline as `create_app()` in `app.py`, and `app = create_app()` runs **at import time with `DevelopmentConfig` hardcoded** (`app.py:65`) — so gunicorn serves a DEBUG app. There is no env-driven config selection. A cleaner `src/utils/create_app.py` exists but is entirely commented out.
- **No blueprints, no service layer.** ~38 routes and all business logic live in `app.py`, with a pile of module-level "service" helpers at the bottom of the file.
- **Chat turn** (`run_ai_response`, `app.py:1386`): load last N messages from SQL + a rolling summary queue **stored in the Flask session cookie** → run a `context_analyzer` LLM call (gpt-3.5-turbo, deprecated `functions=` API) to pick a tool → optionally chain 4–5 sequential blocking LLM calls for calendar/email/memory → call the persona model → save reply → periodically summarize into Pinecone.
- **Memory:** short-term = recent SQL messages + session-cookie queue; long-term = OpenAI-embedded LLM summaries in Pinecone, retrieved only when the router chooses `remember`.
- **Target architecture** (where the overhaul is taking this): real env-driven app factory, blueprints per domain, a service layer, one unified `LLMProvider` interface, one vector DB, native tool-use instead of the hand-rolled router, short-term memory out of the cookie. Details in `docs/designs/overhaul-and-repositioning.md`.

---

## How to Run

- **Dev server:** `python app.py` (uses `DevelopmentConfig` → SQLite at `src/instance/users.db`, DEBUG on, binds `0.0.0.0:5000`).
- **Prod (as-is, do not trust yet):** `gunicorn app:app` — but this ALSO serves the DEBUG dev app until config selection is fixed (Phase 1).
- **DB bootstrap:** `python db_create.py`. **Migrations are drifted** — regenerate a clean Alembic baseline before relying on `flask db upgrade`.
- **Tests:** `pytest src/tests/` (partial coverage; no CI, no lint/format config).
- **Requires** a populated `.env` (see Environment Variables) — the app imports fine in dev but AI/voice/OAuth/Stripe calls need real keys.

---

## Environment Variables

- **`DB_SECRET_KEY`** — Flask session secret (⚠️ falls back to a hardcoded default; must fail-closed in prod).
- **`DATABASE_URL`** — Postgres URL for prod (⚠️ `config.py` crashes at import if unset).
- **`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_APPLICATION_CREDENTIALS`** — Google OAuth + APIs.
- **`STRIPE_API_KEY`** + Stripe price lookup keys, `YOUR_DOMAIN` — billing.
- **AWS** creds + S3 bucket (referenced `app.py:68-73`); **OpenAI / Anthropic / Google GenAI / Pinecone** API keys.
- **`ADMIN_PASSWORD`** — gates `/admin/reset_credits` (⚠️ hardcoded default; endpoint is otherwise unprotected).

---

## Known Limitations & Gotchas (the "cursed" list)

- **Security (must fix before any deploy):** real user data + plaintext Google OAuth tokens committed in `src/instance/users.db`; hardcoded Azure/ElevenLabs keys in `text_to_speech.py`; DEBUG-on-by-default + weak `SECRET_KEY` default; **privilege escalation** via `GET /add-credits/<amount>`; **auth bypass** on `/send_message` (decorator order); unprotected `/admin/reset_credits`; **IDOR** on `/ai-settings/<id>`; no CSRF anywhere. Full list in the overhaul doc.
- **Billing is broken:** Stripe webhook uses the wrong signature header, `@login_required` on a non-route helper, and grants a non-existent `user.credits` attr. Credit accounting is inconsistent (1500 vs 100 vs 900 across model/reset/pricing).
- **Migration drift:** live DB is at Alembic revision `f961159bf1ce`, which does not exist in `migrations/`; committed migrations don't match current models.
- **Stale AI:** hardcoded model IDs are retired/invalid (`claude-3-5-sonnet-20241022` retired; `claude-3-opus-20241022` never existed; Gemini 1.5 via the deprecated `google.generativeai` SDK). Cross-provider bug at `ai_models.py:148`.
- **Dead weight:** `src/prototypes/`, `src/deprecated/`, commented STT/TTS, empty `google_service.py`, `calendar_utilities.py` dup, `save.txt` files, Azure + desktop-audio deps (`PyAudio`/`keyboard`/`sounddevice`), dual vector DBs, dual deploy configs.
- **Split-brain product:** markets both "productivity assistant" and "emotional companion" simultaneously — the repositioning work resolves this.

---

## Documentation

- **`docs/designs/overhaul-and-repositioning.md`** — full current-state assessment, phased overhaul→production plan, and the strategic repositioning brief. **Start here.**
- **`docs/INDEX.md`** — documentation index.
- **`.context/backlog.md`** — prioritized, actionable work items (security, bugs, tech debt, deploy, strategic spikes).
- **`.context/sprints/bootstrap/sprint.md`** — the first sprint (stabilize, secure, choose a direction).

---

## Source of Truth

This file is the authoritative project context; every session begins here. It reflects the codebase **as inherited** (pre-overhaul). Update it as the overhaul changes architecture, stack, or conventions so it never drifts.
