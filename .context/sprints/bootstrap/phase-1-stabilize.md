# Task Notepad — Phase 1: Stabilize

**Ticket:** task #3 (Phase 1) · **Branch:** `phase-1-stabilize` · **Started:** 2026-07-01
**Scope (from roadmap):** env-driven config + app factory + wsgi.py; BUG-1..12 fixes; credit constants unified; deps pinned/pruned; structured logging + error handlers; Fernet-encrypted OAuth token columns. Alembic baseline DEFERRED until all model edits incl. Phase-4 tables land (roadmap risk #1). CSRF/Talisman/limiter/deploy/health → backlog.

## Plan of commits
1. config.py rewrite + app_factory.py + wsgi.py + extensions consolidation (app.py still imports factory)
2. Model edits: User.is_admin, credit constants, memory_chunk_size fix, EncryptedString tokens
3. BUG-1..5 (S1) fixes in app.py
4. BUG-6..12 fixes (ai_models, email_service, calendar_service, app.py)
5. requirements.txt pin/prune + Aptfile delete
6. Logging pass (print → logging) + error handlers
7. Backlog update (deferred prod items)

## Findings
- **Unaudited bugs found & fixed:** `User.strip_customer_id` typo (billing AttributeError), `GoogleUser.token_expire_at` vs `token_expires_at` used everywhere (Google login crash), template-clone prompt leak in `/onboarding/ai/existing` (any user could clone any AI by id → added `AIModel.is_template` gate), `Message.timestamp` import-time default, import-time client construction crashing bare checkouts (OpenAI/Anthropic/Pinecone → lazy).
- Pre-existing test failures (NOT regressions): `test_context_analyzer.py` requires live OPENAI_API_KEY; `test_date_utils.py` asserts hardcoded 2023 dates. Both handled in Phase 2/3 test overhaul.
- calendar_service imported the dead `google` global but never used it.

## Decisions
**Decision:** Credits reconciled to FREE_CREDITS_DEFAULT=900 (matches pricing copy), PREMIUM_CREDITS_GRANT=10000 (placeholder for "unlimited" pending real metering), MEMORY_CHUNK_SIZE_DEFAULT=6 (256 would effectively disable memory).
**Tier:** 2. **Rationale:** single source of truth in config.py; values chosen from the pricing page as the only user-facing contract. **Reversibility:** constants. **Scope:** config.py, users.py, app.py.

**Decision:** APP_ENV default = development (roadmap said production).
**Tier:** 2. **Rationale:** deployment is deferred; prod requires explicit APP_ENV=production AND fails closed on missing secrets, so the safety property is preserved with better dev ergonomics. **Reversibility:** one-line. **Scope:** config.py.

**Decision:** BUG-9 fixed by deleting the service cache instead of populating it.
**Tier:** 2. **Rationale:** class-level per-user credential cache is a concurrency hazard; service construction is local/cheap. **Alternatives rejected:** per-request caching (no measured need). **Scope:** email_service.py, calendar_service.py.

**Decision:** Alembic baseline deferred to after Phase-4 model additions (LAUNCH-5).
**Tier:** 2. **Rationale:** roadmap risk #1 — baseline must include all model edits or an immediate second migration follows. Dev uses `db.create_all()` meanwhile. **Scope:** migrations/.

## Status: COMPLETE (2026-07-01)
All planned commits landed on `phase-1-stabilize`. Exit verified: app imports without any API keys; DEBUG-safe config selection; prod fails closed; smoke tests pass (send_message auth 302, add-credits 404, admin 302/403, webhook 400 on bad sig).
