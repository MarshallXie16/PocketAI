# Task Notepad — Phase 2: Modularize

**Ticket:** Phase 2 · **Branch:** `phase-2-modularize` (from master) · **Started:** 2026-07-01
**Scope (from roadmap §Phase 2 + brief):** carve 1,600-line `app.py` into app factory + blueprints
+ services; move `extensions` to `src/extensions.py`; move email/calendar services to
`src/services/integrations/`; delete dead code; first-class pytest suite (zero-key green);
docs (architecture.md, README.md, INDEX.md); CI (ruff + pytest). Move-only: behavior, route
PATHS and request/response contracts identical. Preserve every Phase-1 bug fix.

## Plan of commits
1. extensions move (db/migrate/login_manager/oauth) + app_factory + wsgi + template root fix
2. blueprints + services extraction (logical groups)
3. dead-code deletion
4. tests (conftest + 6 test modules + fixed stale tests)
5. docs + CI

## Key findings
- **Template root fix (critical):** `app_factory.py` lives in `src/`, so `Flask(__name__)` would
  root at `src/` and break `template_folder='src/templates'`. Fixed by passing
  `root_path=<project root>` so relative template/static/`current_app.root_path` resolve exactly
  as they did when `app.py` sat at the repo root. Preserves `upload_profile_image`'s root_path join.
- Only **3** template `url_for(endpoint)` refs point at moved routes (rest are `url_for('static',…)`):
  `ai_settings.html` `profile`, `profile.html` `chat`, `onboarding-ai-create.html` `onboarding_ai`.
- `login_manager.login_view` changed from the `/login` path to the `auth.login` endpoint
  (correct for `url_for`; redirect target path unchanged).
- `AI_model_client.py` is used by many live components — kept (NOT in the dead-code list, despite
  the roadmap's broader Phase-2 sketch; brief's explicit list governs).
- Component singletons (`context_analyzer`, `long_term_memory`, `user_calendar`, `user_email`)
  construct key-free at import (Phase-1 lazy clients), so importing the app needs zero keys — the
  test-suite exit criterion is achievable.

## Decisions
**Decision:** OAuth client registration + Flask-Login `user_loader` live in `app_factory.py`;
`src/utils/auth.py` deleted (its `oauth`/`init_oauth` superseded).
**Tier:** 2. **Rationale:** brief puts `oauth` in `extensions.py`; the google-client `register()`
and `@login_manager.user_loader` are factory concerns. **Alternatives rejected:** keep a shrunken
`auth.py` (leaves a one-liner module, more indirection). **Reversibility:** re-add module.
**Scope:** app_factory.py, src/utils/auth.py (deleted).

**Decision:** No new global error handlers added.
**Tier:** 2. **Rationale:** `app.py`'s `create_app` had none; adding 404/500 handlers would change
response bodies, violating the move-only contract. The brief lists "error handlers" in the factory,
but hard-constraint #2 (behavior identical) wins. **Reversibility:** add handlers later.
**Scope:** app_factory.py.

**Decision:** Services keep using Flask context-locals (`current_user`, `session`, `request`,
`current_app`) exactly as the original helpers did, rather than threading everything through
parameters.
**Tier:** 2. **Rationale:** guarantees byte-for-byte behavior in a move-only refactor; Phase 3
rewrites the AI core anyway. **Reversibility:** parameterize later. **Scope:** src/services/*.

## Verification (orchestrator, post-carve)
- Route-path diff vs master: IDENTICAL (37 routes). Templates: no stale `url_for` endpoints. JS: hardcoded paths, unchanged.
- Phase-1 fixes present: `get_owned_ai` gate, `StripeEvent` idempotency, `hmac.compare_digest`, `is_template` clone guard, `form_get`.
- Suite: 34 passed / 21 skipped (live-API modules), zero env vars. Ruff clean. Smoke OK (/, send_message 302, webhook 400).
- Tests (opus agent): 26 new tests + stale date tests root-caused (freezegun froze at UTC midnight = prior day in America/Vancouver) and fixed. Docs+CI (sonnet agent): README, architecture.md, INDEX, ci.yml, pyproject ruff cfg.

## Reviews (constitution: 1 native + 1 external)
- Native (opus): **SAFE TO MERGE.** Nit fixed: dead `LOGIN_URL` removed from config.py (factory sets `login_view='auth.login'`). Pre-existing dangling refs noted (css/profile.css, js/profile.js, /upload_audio) — left for the UI redesign.
- External (codex gpt-5.5, high): findings below.

## For Phase 3
- `src/components/` is the legacy AI core — replaced by `src/providers/` + `src/ai/`; kill the components/* ruff ignores with it.
- Chat tests patch `src.blueprints.chat.run_ai_response` — keep that seam or update tests.
- `AI_model_client.py` still live (components import it) — dies in Phase 3.

## Status: REVIEW — awaiting codex findings, then merge
