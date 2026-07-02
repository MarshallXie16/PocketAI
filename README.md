# PocketAI

PocketAI is a Flask web app that pairs each user with a personalized AI companion: custom persona, episodic long-term memory, and real tool use (Google Calendar, Gmail). The defining behavior is proactive outreach — the companion reaches out first, follows up on commitments, and sends messages before you ask.

**What makes it a companion, not just a chatbot:**
- **Episodic memory** — background retrospective extraction turns conversations into searchable episodes and structured key facts (commitments, events, goals). Composite recall scoring (similarity + recency + reinforcement + importance) surfaces the most relevant memories.
- **Real calendar and email with a confirmation gate** — the companion can read your calendar and inbox, create events, and send emails. Consequential actions (writes) follow a two-step draft/confirm flow; a server-side gate prevents prompt injection from auto-confirming anything.
- **Agent-scheduled proactive check-ins** — the companion schedules its own follow-ups when you make a commitment ("I'll sleep by 11!") or mention something coming up. A nightly planner can also propose 0–2 contextual messages based on your calendar and outstanding facts.
- **Voice in / voice out** — speech-to-text transcription (`gpt-4o-transcribe`) on input; Gemini TTS (`gemini-3.1-flash-tts-preview`, with OpenAI as fallback) for spoken replies.

**Status: active development, not yet deployed.** Phases 3 (AI-core rewrite) and 4 (companion features) are complete on `phase-4-companion`. See `docs/designs/overhaul-roadmap.md` for the full plan.

---

## Quickstart (local dev)

**1. Create a virtual environment and install dependencies.**

```bash
python3 -m venv .venv
pip install -r requirements-dev.txt
```

**2. Configure environment variables.**

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

| Variable | Required to | Notes |
|----------|------------|-------|
| `APP_ENV` | Boot the app | Set to `development` (default if unset) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Chat | At least one AI provider key is needed for actual conversations |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth + Calendar/Gmail | Only needed if testing OAuth or integrations |
| `STRIPE_API_KEY` | Billing | Only needed if testing payments |
| `PROACTIVE_TICK_SECRET` | Proactive outreach | The `/tasks/proactive-tick` endpoint is disabled if this is unset; set to any strong random string |

The app will import and boot without AI keys. Requests that hit an AI endpoint will fail.

**3. Create the development database.**

```bash
./.venv/bin/flask --app wsgi shell
>>> from src.extensions import db
>>> db.create_all()
>>> exit()
```

Note: a proper Alembic baseline migration is pending (LAUNCH-5 in `.context/backlog.md`). `db.create_all()` is the correct bootstrap for now.

**4. Run the development server.**

```bash
./.venv/bin/python wsgi.py
```

The app starts at `http://localhost:5000`.

**5. Run the test suite.**

```bash
./.venv/bin/pytest src/tests/ -q
```

130+ tests collected.

**6. (Optional) Wire the proactive tick.**

To enable proactive check-ins locally, hit the tick endpoint on a schedule (e.g. every 15 minutes with a cron job or `watch`):

```bash
curl -X POST http://localhost:5000/tasks/proactive-tick \
     -H "X-Tick-Secret: <your PROACTIVE_TICK_SECRET value>"
```

In production, configure your platform's cron (Heroku Scheduler, AWS EventBridge, etc.) to POST to `/tasks/proactive-tick` with the `X-Tick-Secret` header every ~15 minutes.

---

## Project structure

```
PocketAI/
├── wsgi.py                     # WSGI entry point (also runs dev server)
├── config.py                   # Config classes + MODEL_REGISTRY + select_config()
├── pyproject.toml              # Ruff + pytest config
├── requirements.txt            # Pinned runtime dependencies
├── requirements-dev.txt        # Adds pytest + ruff
├── docs/                       # Architecture, design docs, index
└── src/
    ├── app_factory.py          # create_app(): extensions, OAuth, blueprints
    ├── extensions.py           # Shared extension singletons (db, login_manager…)
    ├── blueprints/             # Route handlers (thin, delegate to services)
    ├── providers/              # LLMProvider protocol + Anthropic/OpenAI/Gemini adapters + registry
    ├── ai/                     # Agent loop, tools, episodic memory, voice, prompts, background executor
    ├── services/               # Business logic + DB commits
    │   └── integrations/       # Google Calendar + Gmail adapters
    ├── models/                 # SQLAlchemy model definitions
    ├── utils/                  # Auth helpers, forms, utilities
    ├── templates/              # Jinja2 server-rendered pages
    ├── static/                 # CSS, JS, images
    └── tests/                  # pytest test files
```

---

## Documentation

- `docs/architecture.md` — request flow, AI-core detail, confirmation gate, episodic memory, proactive outreach, module map, conventions, how-to recipes
- `docs/designs/overhaul-roadmap.md` — phased overhaul plan (Phases 0–4) and product identity
- `docs/designs/design.md` — brand and UI design direction
- `docs/INDEX.md` — full documentation index
- `.context/project.md` — tech stack, known limitations, current architecture
- `.context/backlog.md` — prioritized work items (LAUNCH-1..5 are pre-deploy requirements)
