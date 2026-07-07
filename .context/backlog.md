# Backlog

**Last updated:** 2026-07-06 (post Phase-5 + docs-housekeeping)
**Size cap:** ~120 lines. Full pre-overhaul audit (every original SEC/BUG/PROD/AI/DEBT/STRAT item with line refs) is archived at `.context/archive/backlog-audit-2026-07-01.md`.

Roadmap: `docs/designs/overhaul-roadmap.md`. Severity: **S1 critical → S4 minor**.

---

## ✅ Done (Phases 0–5, merged to master)
- **Phase 0–1** — secrets purged from history + `.gitignore` hardened (SEC-2); Fernet-encrypted OAuth tokens (SEC-3); all 12 audited bugs fixed (BUG-1..12); env-driven fail-closed config (PROD-1); deps pinned/pruned (DEBT-1).
- **Phase 2** — app-factory + blueprints + services (DEBT-3); dead code deleted (DEBT-2); `docs/architecture.md`, `README`, test suite (177 tests).
- **Phase 3** — model registry / current IDs (AI-1); `LLMProvider` protocol + adapters (AI-2); hand-rolled native tool-use loop (AI-3); DB `ConversationState` short-term memory off the cookie (DEBT-4); background thread pool.
- **Phase 4** — episodic memory (pgvector-ready), relationship model, proactive outreach, voice I/O (STT + Gemini/OpenAI TTS) (STRAT-3/4). Identity confirmed: "a companion that acts" (STRAT-1).
- **Phase 5 (2026-07-03)** — Flask/Jinja frontend rebuild on the `pocket.css` design system; UI-1..4 all landed; dual-reviewed. Tag `phase-5-frontend-complete`.
- **Docs-housekeeping (2026-07-06)** — `docs/architecture.md` refreshed for Phase 5; new `docs/frontend.md`; module docstrings on the 10 bare modules; 5 orphaned JS files removed; this backlog consolidated.

---

## 🚀 Pre-launch requirements (deferred by maintainer priority — MUST land before public deploy)
- **LAUNCH-1 — CSRF**: Flask-WTF `CSRFProtect` + `{{ csrf_token() }}` in forms + `X-CSRFToken` header in the fetch sites (`chat.js`, `settings.js`, `user-contacts.js`); exempt the Stripe webhook. Land atomically with template updates. **Agent-doable now (no secrets).** S2.
- **LAUNCH-2 — Cookie/transport hardening**: `ProxyFix`, HTTPS enforce + security headers (Talisman), rate limiting (Flask-Limiter) on login/signup/AI/webhook. (Secure/HttpOnly/SameSite already in ProductionConfig.) Pairs with LAUNCH-3. S2.
- **LAUNCH-3 — Deploy target** (maintainer decision): Dockerize (slim + gunicorn) → managed Postgres + S3; delete the Heroku (`Procfile`/`runtime.txt`) and EB (`.ebextensions/`) loser's artifacts; add `/health`. No Sentry. S2.
- **LAUNCH-4 — IP roster + "uncensored" tier** (maintainer decision, STRAT-2): replace copyrighted roster with original characters (re-seed `is_template=True` rows — old ones were discarded with the DB); drop the "Uncensored Models" pricing bullet; restore Gemini safety settings. Legal/payments risk. S2.
- **LAUNCH-5 — Alembic baseline**: all Phase-4 tables are final — delete the 2 stale revisions, `flask db revision --autogenerate -m baseline` against an empty DB, review SQLite→Postgres types. **Agent-doable now.** S2.
- **LAUNCH-6 — Live-key verification** (needs a populated `.env`): pipeline is mock-tested only. One real chat turn per provider; calendar/email tool round-trip incl. draft→confirm; proactive tick end-to-end; TTS (Gemini + fallback) + `/transcribe`. Verify `gpt-5-mini`/`gemini-3-pro-preview` pricing in `MODEL_REGISTRY` (flagged unverified). Gates deploy.

**SEC-1 (maintainer action):** the Google OAuth tokens + Azure/ElevenLabs keys once in git history were scrubbed from the tree/history, but **rotation/revocation is a separate manual step** — revoke at myaccount.google.com/permissions and regenerate the API keys if those accounts still exist. The maintainer's call; the purge itself is done.

---

## 🎯 Frontend framework
- **FE-REACT** — migrate Flask/Jinja → React, eventual (maintainer-directed 2026-07-03). Proposal: `docs/designs/react-migration-proposal.md` (Tier 3, draft — recommends Vite+React islands, strangler, chat first). **No implementation until sign-off.** Stay Jinja meanwhile.

---

## 🔧 Tech debt (post-overhaul, non-blocking)
- **DEBT-5** — proactive tick: real job queue + per-user fairness (currently bounded batch/tick, FIFO by `scheduled_for`); DST-ambiguous daily-checkin times (zoneinfo fold). S3.
- **DEBT-6** — integrations cleanup: email/calendar services still carry legacy enum-date methods (unused by the tool layer) + ruff per-file-ignores. S3.
- **DEBT-7** — pgvector ranking swap once managed Postgres exists (`MemoryStore` interface ready; in-Python cosine fine at current scale). S3.
- **DEBT-8** — frontend tidy: inline `<script>` duplication (the `is-selected` chip toggle repeats across settings.js + 3 onboarding templates); legal pages may still carry pre-redesign markup. Fold into the React migration or do standalone. S4.

---

## Maintenance
Keep under ~120 lines. Close items as sprints absorb them; promote anything architectural to `project.md`. Historical detail lives in `.context/archive/`.
