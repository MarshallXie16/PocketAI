# PocketAI

PocketAI is a Flask web app that pairs each user with a personalized AI companion: custom persona, persistent long-term memory, and real tool use (Google Calendar, Gmail, contacts). The defining behavior is proactive outreach — the companion reaches out first, follows up on commitments, and sends messages before you ask.

**Status: active overhaul, not yet deployed.** The codebase is being modularized (Phase 2 is on `phase-2-modularize`), with AI-core modernization and companion features planned in Phases 3–4. See `docs/designs/overhaul-roadmap.md` for the full plan.

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

---

## Project structure

```
PocketAI/
├── wsgi.py                     # WSGI entry point (also runs dev server)
├── config.py                   # Config classes + select_config() (APP_ENV-driven)
├── pyproject.toml              # Ruff + pytest config
├── requirements.txt            # Pinned runtime dependencies
├── requirements-dev.txt        # Adds pytest + ruff
├── docs/                       # Architecture, design docs, index
└── src/
    ├── app_factory.py          # create_app(): extensions, OAuth, blueprints
    ├── extensions.py           # Shared extension singletons (db, login_manager…)
    ├── blueprints/             # Route handlers (thin, delegate to services)
    ├── services/               # Business logic + DB commits
    │   └── integrations/       # Google Calendar + Gmail adapters (moved from components/)
    ├── components/             # Legacy AI core — being replaced in Phase 3
    ├── models/                 # SQLAlchemy model definitions
    ├── utils/                  # Auth helpers, forms, utilities
    ├── templates/              # Jinja2 server-rendered pages
    ├── static/                 # CSS, JS, images
    └── tests/                  # pytest test files
```

---

## Documentation

- `docs/architecture.md` — request flow, module map, conventions, how-to recipes
- `docs/designs/overhaul-roadmap.md` — phased overhaul plan (Phases 0–4) and product identity
- `docs/designs/design.md` — brand and UI design direction
- `docs/INDEX.md` — full documentation index
- `.context/project.md` — tech stack, known limitations, current architecture
- `.context/backlog.md` — prioritized work items (LAUNCH-1..5 are pre-deploy requirements)
