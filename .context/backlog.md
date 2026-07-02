# Backlog

**Last updated:** 2026-07-01 (post Phase-1)
**Size cap:** ~200 lines

Prioritized, actionable work for the PocketAI overhaul. Roadmap: `docs/designs/overhaul-roadmap.md`. Severity: **S1 critical → S4 minor**.

## ✅ Absorbed by Phase 0–1 (2026-07-01, branch `phase-1-stabilize`)
SEC-2 (purge + history rewrite), SEC-3 (Fernet-encrypted tokens), BUG-1..12 (all fixed; BUG-9 fixed by removing the dead cache), PROD-1 (env-driven config, fail-closed prod), DEBT-1 (deps pinned/pruned). Also fixed beyond the audit: `strip_customer_id`/`token_expires_at` column typos, template-clone prompt leak (`AIModel.is_template` gate), Stripe webhook secret in history (scrubbed), import-time client crashes (lazy clients), stale `Message.timestamp` default.

## 🚀 Pre-launch requirements (deferred from Phase 1 by maintainer priority — MUST land before public deploy)
- **LAUNCH-1 — CSRF protection**: Flask-WTF CSRFProtect + `{{ csrf_token() }}` in forms + `X-CSRFToken` header in the ~8 fetch() sites (`chat.js`, `chat-improved.js`, `user-contacts.js`, `profile.html`); exempt the Stripe webhook. Must land atomically with template updates.
- **LAUNCH-2 — Cookie/transport hardening**: Secure/HttpOnly/SameSite cookies (already in ProductionConfig), ProxyFix, HTTPS enforcement + security headers (Talisman), rate limiting (Flask-Limiter) on login/signup/AI calls/webhook.
- **LAUNCH-3 — Deploy target**: Dockerfile (python-slim + gunicorn) → managed Postgres + S3; delete Heroku (`Procfile`, `.slugignore`, `runtime.txt`) and EB (`.ebextensions/`, `.ebignore`) artifacts once chosen. `/health` endpoint + uptime monitoring (maintainer: no Sentry).
- **LAUNCH-4 — IP character roster + "uncensored" tier** (STRAT-2): replace copyrighted roster with original characters; drop "Uncensored Models" pricing bullet (`pricing.html:176`); restore Gemini safety settings (`ai_models.py` BLOCK_NONE). Roster must be re-seeded as `is_template=True` rows regardless (old template rows were discarded with the DB).
- **LAUNCH-5 — Alembic baseline**: regenerate single clean baseline AFTER Phase-4 tables land (dev uses create_all meanwhile).

---

## 🔴 Security (Phase 0 — do first; several are Tier 4 / human action)

### SEC-1 — Rotate exposed credentials committed to git
- **What:** `src/instance/users.db` (tracked) holds 2 real users + **2 Google OAuth rows with plaintext access & refresh tokens**. `text_to_speech.py:29` (Azure key) and `:108` (ElevenLabs key) are hardcoded, even though the file is commented out. All are in git history.
- **Action:** Revoke/rotate the Google tokens and both API keys now. Audit for any other committed keys.
- **Severity:** S1. **Blocks:** any deploy, SEC-2.

### SEC-2 — Purge committed databases from tree + history
- **Where:** `src/instance/users.db`, `src/db/chroma.sqlite3`, Chroma HNSW `*.bin`.
- **What:** Decide keep-vs-discard the data (2 users / 125 messages / 17 embeddings). Then `git rm --cached` + scrub history (`git filter-repo`/BFG). `.gitignore` already lists these but they were committed earlier, so still tracked.
- **Severity:** S1. **Depends on:** SEC-1.

### SEC-3 — Encrypt OAuth tokens at rest
- **Where:** `src/models/google_user.py:8-9` (plain `String`).
- **What:** Encrypt token columns (Fernet/KMS) so a future DB leak doesn't expose live Google sessions.
- **Severity:** S2.

---

## 🐞 Bugs (correctness & security)

### BUG-1 — Privilege escalation: `GET /add-credits/<amount>`
- **Where:** `app.py:1103`. Any logged-in user grants themselves unlimited credits via GET (CSRF-able). **Severity:** S1.

### BUG-2 — Auth bypass on `/send_message`
- **Where:** `app.py:279` — `@login_required` above `@app.route` ⇒ never applied. `try/except` also commented out (`:336`). **Severity:** S1.

### BUG-3 — Unprotected admin endpoint
- **Where:** `app.py:1110` `/admin/reset_credits` — no `@login_required`, hardcoded default password (`:1100`), non-constant-time compare. **Severity:** S1.

### BUG-4 — IDOR on `/ai-settings/<id>`
- **Where:** `app.py:487` — no ownership check (GET or POST); any user reads/overwrites any AI's settings. Fix with a shared ownership helper applied to every id-from-URL route. **Severity:** S1.

### BUG-5 — Stripe fulfillment broken (paid credits never granted)
- **Where:** `app.py:975` webhook reads `STRIPE_SIGNATURE` (should be `Stripe-Signature`); `handle_checkout_session` (`:1008`) has `@login_required` on a non-route helper; `update_user_subscription` (`:1039`) grants non-existent `user.credits`. **Severity:** S1.

### BUG-6 — Cross-provider attribute error breaks GPT path
- **Where:** `ai_models.py:148` reads `response.candidates[0].finish_reason` (a Gemini attr) on an OpenAI response → `AttributeError`. **Severity:** S2.

### BUG-7 — `regenerate_message` deletes wrong rows
- **Where:** `app.py:374` — unordered `timestamp >= message.timestamp` selection; client/DB can diverge in a credit-charging path. **Severity:** S2.

### BUG-8 — Self-comparison in contacts lookup
- **Where:** `email_service.py:230` — `Contacts.query.filter(user_id == user_id, ...)` compares a param to itself (always true); should be `Contacts.user_id == user_id`. **Severity:** S2.

### BUG-9 — Service auth cache never populated
- **Where:** `email_service.py:135-162`, `calendar_service.py:115-139` — `_service_cache` checked but never written ⇒ re-auth every call; also class-level dict shared across users (concurrency hazard). **Severity:** S3.

### BUG-10 — Unvalidated input → 500s
- **Where:** many handlers do `request.form.get('x').strip()` / `data['x']` with no guard (e.g. `app.py:102,131,822`; `edit_contact` `:915`). Add a validation layer (WTForms/pydantic). **Severity:** S3.

### BUG-11 — Dead `google` global
- **Where:** `app.py:24` imports `google` while still `None`; token refresh (`:1301`) calls a method on `None`. **Severity:** S3.

### BUG-12 — `memory_chunk_size` default mismatch
- **Where:** `app.py:1358` (6) vs `src/models/users.py:123` (256). Reconcile. **Severity:** S3.

---

## ⚙️ Production-readiness / Config (Phase 1)

### PROD-1 — Config selection + prod hardening
- **What:** Env-driven config so `ProductionConfig` is used; remove import-time `app = create_app()` (`app.py:65`); fix `DATABASE_URL` crash (`config.py:33`); fail-closed `SECRET_KEY`; `DEBUG=False` in prod. **Severity:** S1.

### PROD-2 — CSRF, cookie hardening, headers, rate limiting
- **What:** Flask-WTF CSRF; `Secure`/`HttpOnly`/`SameSite`; `ProxyFix`; HTTPS enforce; Flask-Talisman headers; Flask-Limiter (esp. webhook + AI calls). **Severity:** S2.

### PROD-3 — Regenerate Alembic migration baseline
- **What:** Live rev `f961159bf1ce` not in repo; committed migrations don't match models. Regenerate clean baseline before `flask db upgrade`. **Severity:** S2.

### PROD-4 — Logging, error handlers, healthcheck, monitoring
- **What:** Replace all `print()` with structured logging; add `@app.errorhandler`s + `/health`; wire Sentry/APM. **Severity:** S2.

### PROD-5 — Choose one deploy target
- **What:** Repo has conflicting Heroku + AWS EB configs. Recommend Dockerize → Render/Railway/Fly (managed Postgres + S3); delete the loser's artifacts. **Severity:** S2.

---

## 🧹 Technical Debt (Phases 1–2)

### DEBT-1 — Dependency cleanup
- **What:** Pin all deps (currently 0/31 pinned); remove desktop-audio libs + duplicate `AudioRecorder`; remove unused Azure stack; delete `Aptfile`; drop dead vector-DB dep; add missing `anthropic`/Google-GenAI/`beautifulsoup4`. **Effort:** 3–4h. **Severity:** S2.

### DEBT-2 — Delete dead code
- **Where:** `src/prototypes/`, `src/deprecated/`, commented `speech_to_text.py`/`text_to_speech.py`, empty `google_service.py`, `calendar_utilities.py`, `ms_voice.py`, `audio_record.py`, `create_app.py`, `save.txt` (root + deprecated). **Effort:** 2h. **Severity:** S3.

### DEBT-3 — Modularize the monolith
- **What:** App factory + blueprints (`pages/auth/chat/ai/profile/contacts/billing/admin`) + service layer; one transaction per request; ownership-check helper. **Effort:** 1–2 weeks. **Severity:** S2 (maintainability).

### DEBT-4 — Short-term memory out of the session cookie
- **Where:** `app.py:1390-1472` — rolling queue in Flask session; not multi-worker safe, cookie-size bound. Move to Redis/DB. **Effort:** 1–2d. **Severity:** S3.

---

## 🤖 AI Modernization (Phase 3)

### AI-1 — Current model IDs, centralized in config
- **What:** Replace retired/invalid IDs (`claude-3-5-sonnet-20241022` retired; `claude-3-opus-20241022` never existed; Gemini 1.5). Map tiers to `claude-opus-4-8` / `claude-fable-5` / `claude-sonnet-4-6` / `claude-haiku-4-5`. Centralize in `config.py`; rebuild `calculate_cost` to fail soft. **Severity:** S2.

### AI-2 — Unify multi-provider behind one interface
- **What:** `LLMProvider` protocol + thin adapters; structured message blocks instead of string-concat (`ai_models.py:130/187/243`); modernize Anthropic call (streaming, adaptive thinking). **Effort:** 3–5d.

### AI-3 — Replace hand-rolled router with native tool-use
- **What:** Collapse the multi-hop gpt-3.5/gpt-4o-mini `functions=` cascade into a single native tool-use loop (calendar/email/memory as tools). Biggest latency + quality win. **Effort:** 3–5d.

### AI-4 — Consolidate to one vector DB + de-block request path
- **What:** Pick Pinecone or Chroma; remove `save.txt` write (`memory.py:86`); move voice gen + memory write to background tasks. **Effort:** 3–5d.

---

## 🧭 Strategic Spikes (Track B — see design doc §6)

### STRAT-1 — Confirm the product direction
- **What:** Decide the identity: recommended "a companion that actually acts" (assistant↔companion gap), vs. pure companionship, vs. a niche vertical wedge. Maintainer sign-off required. **Blocks:** all Track-B feature work.

### STRAT-2 — Resolve IP + "uncensored" liabilities
- **What:** Prebuilt roster uses copyrighted anime/VTuber characters; PocketAI+ advertises "Uncensored Models" (moderation/payments/app-store risk). Replace roster with original characters; decide moderation stance before marketing. **Severity:** S2 (legal/payments risk).

### STRAT-3 — Ship voice input (STT)
- **What:** The mic button exists but STT is fully commented out — the biggest missing piece for a companion. Implement a real STT path (streaming) once direction is confirmed.

### STRAT-4 — Proactive presence + relationship model
- **What:** "Initiate conversations" (already on the old roadmap), scheduled check-ins, lightweight affinity/relationship state, mobile/push. Retention mechanics for the companion-that-acts vision.

---

## Maintenance
Keep this under ~200 lines. Close items as sprints absorb them; promote anything architectural to `project.md`. Re-derive severities as the code changes.
