# PocketAI — Overhaul & Repositioning Plan

**Last updated:** 2026-07-01
**Status:** Draft for review — the strategic direction (§6) is a *proposal* for the maintainer + Fable to refine, not a locked decision.
**Audience:** Fable (and any agent) driving the overhaul. This is the north-star document.

---

## 1. Executive Summary

PocketAI is a Flask app that gives users personalized AI assistants with **persona customization, persistent long-term memory, real tool use (calendar/email/contacts), and voice output**. It was genuinely ahead of its time (~2022–2024) but is now surrounded by commoditized competitors (ChatGPT/Claude memory + connectors, Character.ai personas, OpenRouter model routing).

The work has two intertwined tracks:

- **Track A — Technical overhaul → production.** The code is a ~1,600-line monolith with real security holes (committed credentials, DEBUG-in-prod, auth-bypass/IDOR/privilege-escalation bugs), broken billing, drifted migrations, and stale AI model IDs. It must be secured, stabilized, modularized, and modernized before it can safely go live again.
- **Track B — Strategic repositioning.** The product is "split-brained" — it markets both a productivity assistant and an emotional companion. Its most *differentiated* assets are the companion-style ones (persona + memory + roleplay/texting modes + voice + prebuilt characters) combined with something companions lack: **real agency in the user's life** (calendar/email/contacts). That combination is the wedge. §6 proposes directions.

**Guiding sequencing principle:** secure first, stabilize second, modularize third, modernize the AI core fourth, then build the differentiated product. Do not skip Phase 0.

---

## 2. Current-State Assessment

**What genuinely works today:** email/password + Google OAuth login; persona creation & multi-assistant ownership; a working chat loop with a hand-rolled agentic tool router; Pinecone long-term memory with an LLM "is this worth remembering?" gate; Google Calendar (read + create) and Gmail (read + send); contacts CRUD; OpenAI TTS voice output uploaded to S3; Stripe checkout (up to the broken webhook).

**What's stubbed or dead:** voice input / STT (mic button exists, backend fully commented out); Chroma vector backend (commented out); a large desktop-audio prototype (`src/deprecated/`, `src/prototypes/`); multi-provider TTS scaffold (`text_to_speech.py`, commented).

**Overall:** an ambitious, feature-rich prototype with prototype-grade plumbing. High-value bones, unsafe skin.

---

## 3. 🔴 Phase 0 — Security & Credential Triage (BLOCKER — do before anything else)

These involve **real exposed secrets** and require human decisions (rotation, history rewrite). Treat as Tier 4.

1. **Rotate exposed credentials.** `src/instance/users.db` (committed & tracked) contains 2 users and **2 Google OAuth rows with plaintext `access_token` + `refresh_token`**. Rotate/revoke those Google tokens now. Also rotate the hardcoded **Azure key (`text_to_speech.py:29`)** and **ElevenLabs key (`text_to_speech.py:108`)** — they're in history even though the file is commented out. Rotate any API key ever committed.
2. **Purge committed data from the repo + history.** Remove `src/instance/users.db`, `src/db/chroma.sqlite3`, and the Chroma HNSW index from the working tree (`git rm --cached`) and scrub history (`git filter-repo` / BFG). Decide first whether to preserve the data (migrate 2 users / 125 messages / 17 embeddings into a real managed DB) or discard it. `.gitignore` already lists these paths, but they were committed before the rules, so they're still tracked.
3. **Encrypt OAuth tokens at rest.** `google_user.access_token`/`refresh_token` are plain `String` columns (`google_user.py:8-9`). Encrypt (Fernet/KMS) going forward.

**Exit criteria:** no secrets in the working tree or history; exposed tokens rotated; token storage encrypted.

---

## 4. Phase 1 — Stabilize & Make It Safe to Deploy

**Config & runtime**
- Drive config from an env var so `ProductionConfig` is actually used; kill import-time `app = create_app()` with hardcoded `DevelopmentConfig` (`app.py:65`).
- Fix `config.py:33` crash when `DATABASE_URL` is unset (`.replace` on `None`); handle the `postgres://`→`postgresql://` prefix defensively.
- Fail-closed `SECRET_KEY` (raise if unset in prod); ensure `DEBUG=False` in prod (currently exposes the Werkzeug debugger = RCE).

**Critical correctness/security bugs (all in `app.py` unless noted)**
- `GET /add-credits/<amount>` (1103) — any user grants themselves unlimited credits. Remove/relock.
- `/send_message` (279) — `@login_required` above `@app.route` ⇒ auth never applied; also its `try/except` is commented out (336). Fix decorator order + error handling.
- `/admin/reset_credits` (1110) — unprotected, hardcoded default password, non-constant-time compare. Real admin auth.
- `/ai-settings/<id>` (487) — **IDOR**, no ownership check on GET or POST. Add an ownership-check helper and apply it everywhere an `id` is taken from the URL.
- Stripe webhook (975) — wrong header (`STRIPE_SIGNATURE` vs `Stripe-Signature`), `@login_required` on the non-route helper `handle_checkout_session` (1008), and grants a non-existent `user.credits` attr (1039). Rebuild fulfillment; reconcile the credit model.
- Add CSRF protection (Flask-WTF), session cookie hardening (`Secure`/`HttpOnly`/`SameSite`), `ProxyFix`, HTTPS enforcement, security headers, and rate limiting (Flask-Limiter) — especially on the webhook and paid AI calls.

**Data & deps**
- Regenerate a clean Alembic baseline from current models (migrations are drifted; live rev `f961159bf1ce` isn't in the repo).
- Pin every dependency; remove desktop-audio libs (`PyAudio`/`keyboard`/`sounddevice`/`soundfile`/`SpeechRecognition`/`AudioRecorder`×2) and the unused Azure stack; delete `Aptfile`; drop the duplicate/dead vector-DB dep once one backend is chosen; add missing imports (`anthropic`, a Google GenAI SDK, `beautifulsoup4`).

**Observability**
- Replace all `print()` with structured logging; add `@app.errorhandler`s and a `/health` endpoint; wire error monitoring (e.g. Sentry).

**Deploy target — pick ONE (recommend containerizing).** The repo ships conflicting Heroku + AWS EB configs; neither is deploy-ready. Recommended: add a `Dockerfile` (slim-python + gunicorn; no apt packages once desktop audio is gone) and deploy to a modern PaaS (Render / Railway / Fly.io, or AWS App Runner if AWS is mandated), with **managed Postgres** and **S3**. Delete the losing target's artifacts. Lower-effort fallback: return to Heroku (paid dynos now) and delete `.ebextensions`/`.ebignore`.

**Exit criteria:** boots under `ProductionConfig` with `DEBUG=False`; the six critical bugs closed; CSRF + cookie hardening + rate limiting in place; clean migration baseline; pinned/pruned deps; one deploy target; logging + healthcheck live.

---

## 5. Phases 2–3 — Modularize, then Modernize the AI Core

**Phase 2 — Modularization (maintainability).** Break the monolith along seams that already exist:
- Real `src/app_factory.py` (env-driven); make S3/Stripe first-class instead of import-time module state; fix the permanently-`None` `google` global (`app.py:24`); delete the stray Flask app in `extensions.py` and the dead `create_app.py`.
- **Blueprints:** `pages`, `auth` (incl. all Google routes), `chat`, `ai`, `profile`, `contacts`, `billing`, `admin`.
- **Service layer** (`src/services/`): `Auth/Session`, `AIConversation`, `User`, `AIModel` (with the shared ownership check), `Contact`, `Billing`, `Storage`. One transaction boundary per request instead of scattered per-helper commits.
- Move short-term conversation memory out of the Flask session cookie into Redis/DB (multi-worker safe).
- Fix correctness bugs: cross-provider attr `ai_models.py:148`; self-comparison `email_service.py:230`; the never-populated `_service_cache` (email/calendar); `regenerate_message` deletes the wrong rows (unordered `>=`, `app.py:374`); `memory_chunk_size` default mismatch (6 vs 256).

**Phase 3 — AI-core modernization.**
- **Unify providers** behind one `LLMProvider` protocol (`generate(system, messages, tools, stream)`), with thin adapters. Pass retrieved context/tool output as **structured message blocks**, not string-concatenated into the last user message (`ai_models.py:130/187/243`).
- **Current model IDs, centralized in config** (they're hardcoded & stale across `ai_models.py`, `context_analyzer.py`, `utils.py`). Anthropic tiers → **`claude-opus-4-8` (Opus 4.8)**, **`claude-fable-5` (Fable 5)**, `claude-sonnet-4-6`, `claude-haiku-4-5` (IDs are complete — no date suffixes). Migrate the retired/invalid ones. Modernize the Anthropic call (drop params that 400 on Opus 4.8; use adaptive `thinking` where it helps; stream for large `max_tokens`). Migrate `google.generativeai` → `google-genai` if Gemini stays. Rebuild `calculate_cost` to fail soft, not `KeyError`.
- **Replace the hand-rolled intent router** (multi-hop gpt-3.5/gpt-4o-mini `functions=` cascade) with a **single native tool-use loop** — the biggest latency and quality win.
- **Consolidate to one vector DB**; remove the `save.txt` debug write (`memory.py:86`).
- **De-block the request path:** async or background tasks for voice generation and memory summarization/write; don't serialize 5 network round-trips inside one chat turn.
- Reconcile credit accounting end-to-end (model defaults vs `reset_credits` vs pricing copy vs Stripe grant).

**Exit criteria:** monolith replaced by factory + blueprints + services; one provider interface on current models; one vector DB; native tool-use loop; chat turn no longer fully serialized; correctness bugs closed.

---

## 6. Strategic Repositioning Brief (proposal)

### 6.1 The problem
The original wedges — memory, custom personas, calendar/email tool-use, multi-model routing, voice — are all now commoditized by ChatGPT, Claude, Character.ai, and aggregators. Competing head-on as "another AI assistant" is a losing game for a solo maintainer. PocketAI needs an identity a big lab *won't* naturally occupy.

### 6.2 The insight — the gap is real and PocketAI already straddles it
- **Task assistants (Claude/ChatGPT)** can *do things* but are stateless and impersonal — they don't know you or maintain a relationship.
- **Virtual companions (Character.ai/Replika)** have personality, memory, and emotional continuity but **can't do anything** in the real world — no calendar, no email, no action.
- **PocketAI already has both halves:** a persona/companion layer (custom personality, roleplay + texting modes, voice, prebuilt characters, emotionally-framed system prompt) **and** real agency (Google Calendar/Gmail/contacts execution) with per-character persistent memory. Almost nobody ships both.

### 6.3 Recommended direction — "a companion that actually acts"
Position PocketAI as a **persistent, personalized AI presence that both maintains a relationship with you and takes real action in your life** — remembers your world, and can schedule, remind, email, and (eventually) proactively reach out. It is warmer than an assistant and more useful than a companion.

This direction is recommended because it (a) sits in the defensible gap, (b) reuses the strongest existing assets, and (c) turns the current split-brain from a weakness into the actual value proposition. The retention model is **relationship + utility**, not novelty.

*What it would need built* (Phase 4 candidates): voice **input** (STT — currently the biggest missing piece for a companion), proactive/scheduled outreach ("initiate conversations" is already on the old roadmap), a lightweight relationship/affinity model, and mobile/push for an "always there" presence.

### 6.4 Alternatives considered
- **Pure companionship / character chat (Character.ai competitor).** Big market, but brutal competition, and the current implementation carries real liabilities: the prebuilt roster uses **copyrighted IP characters**, and the "**Uncensored Models**" tier is a moderation / trust-&-safety / payments risk (Stripe and app stores restrict NSFW). Keep the companion *mechanics* as an asset; do **not** make unmoderated character chat the identity.
- **Niche vertical companion-assistant.** Pick one audience (e.g. an ADHD-friendly life-coach companion, a language-learning partner, a "second brain" for a specific community) as a go-to-market wedge on top of §6.3. Narrower = easier to win and to market. A strong option for *first* launch even if the long-term vision is broader.

### 6.5 Recommendation for Fable
Adopt §6.3 as the north-star identity, and evaluate a §6.4 niche as the initial go-to-market wedge. Before building Track-B features, resolve the IP-character roster and the "uncensored" positioning. Treat the final identity as a **decision the maintainer signs off on** — this brief is the input, not the verdict.

---

## 7. Suggested Roadmap (phases → sprints)

Sprints are planned one at a time (per the constitution). This is an indicative sequence, not a frozen plan:

1. **Sprint `bootstrap` (planned):** Phase 0 security triage + confirm strategic direction. See `.context/sprints/bootstrap/sprint.md`.
2. **Sprint `stabilize`:** Phase 1 — config, critical bugs, CSRF/hardening, migration baseline, deps, deploy target, logging/health. Ends with a safe re-deploy of the *current* feature set.
3. **Sprint `modularize`:** Phase 2 — factory + blueprints + services + correctness bugs.
4. **Sprint `modernize-ai`:** Phase 3 — provider interface, current models, native tool-use, one vector DB, de-blocked request path.
5. **Sprint(s) `reposition`:** Phase 4 — build the differentiated product per the §6 decision (e.g. STT, proactive outreach, relationship model), plus IP/uncensored cleanup.

Detailed, actionable items for each live in `.context/backlog.md`.
