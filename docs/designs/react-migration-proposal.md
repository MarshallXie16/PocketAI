# React Migration Proposal (DRAFT — Tier 3, awaiting sign-off)

**Status:** DRAFT. Proposal only — no implementation until the maintainer approves an approach and a sprint.
**Decision tier:** 3 (cross-cutting, partially reversible — new build toolchain + route contract changes).
**Author:** agent, 2026-07-03.
**Directive:** maintainer, 2026-07-03 — "keep to Flask/Jinja for now, but launch an investigation and write a proposal to migrate to React… we need to eventually move to React anyways."

> §2 inventory is from a read-only codebase survey (2026-07-03). Two findings are actionable **before** any React work and independent of it: (a) delete 5 orphaned/dead JS files (§2.2); (b) CSRF is unwired (§2.5) — it's already pre-launch item PROD-2 and must land regardless.

---

## 1. Why migrate (and why not yet)

**The pull toward React.** The chat surface is already a de-facto component system hand-written in vanilla JS — `chat.js` builds DOM trees imperatively (`assistantMessage`, `renderDraftCard`, `voiceBubbleEl`), reconciles server state (pending-action draft card), and manages local UI state (sending flag, mic recorder lifecycle, load-more cursor). This is exactly the class of problem React exists to make declarative. As the companion features grow (richer memory views, live proactive notifications, calendar surfaces), imperative DOM reconciliation gets progressively harder to keep correct — the review already caught several state-sync bugs (message-id wiring, draft-card lifecycle, double-start races) that a declarative render would make structurally impossible.

**Why not now.** The Flask/Jinja rebuild just shipped (Phase 5), is dual-reviewed, and works. A React migration is a multi-week effort that touches the server↔client contract for every interactive route and introduces a build toolchain the project has never had. Doing it immediately would throw away a freshly-verified UI for no user-facing gain. The right time is when a *new* feature would benefit enough to justify starting the strangler migration on that surface.

**Guiding principle: strangler, not rewrite.** Do not rewrite the app. Migrate one surface at a time behind the existing Flask routing, newest/most-interactive first, so each step ships independently and is reversible.

---

## 2. Current-state inventory

No `package.json`, bundler, or `node_modules`. All JS is hand-written vanilla; CSS is one 947-line hand-rolled design system (`pocket.css`). Every page template extends `_base.html`.

### 2.1 Templates (`src/templates/`)
`_base.html` (72) = layout shell (head, auth-gated nav, flash stack, `main.page`, footer, empty `{% block scripts %}`). `_components.html` (56) = macros: `monogram`, `companion_bubble`, `user_bubble`, `reached_out_header`, `action_chip`, `draft_card`.

Page templates by interactivity:
- **External JS:** `chat.html` (480 → `chat.js`), `settings.html` (227 → `settings.js`), `user-contacts.html` (128 → `user-contacts.js`).
- **Inline `<script>`:** `profile.html` (212), `ai_settings.html` (145), `onboarding-ai-create.html` (208), `onboarding-world.html` (180), `onboarding-ai-existing.html` (99), `onboarding-user.html` (101), `signup.html` (76), `login.html` (49) — mostly avatar-preview, password toggle, chip/card pickers, live monogram.
- **Static (no scripts):** `index`, `pricing`, `privacy-policy`, `terms-of-service`, `payment-success`, `payment-canceled`, `error`, `onboarding-ai`.

### 2.2 JS modules (`src/static/js/`)
Only **3 are actually loaded** by templates: `chat.js` (690), `settings.js` (176), `user-contacts.js` (153). **5 are orphaned/dead** (zero `<script src>` hits): `ai-settings.js` (68), `audio.js` (117, WIP, calls a non-existent `/upload_audio`), `signup.js` (59), `script.js` (19), `index.js` (0, empty). → **Pre-migration cleanup: delete the 5 orphans (DEBT).** Their live functionality was reimplemented as inline scripts.

Component-shaped imperative DOM builders already present: `chat.js` `assistantMessage`/`renderDraftCard`/`voiceBubbleEl`/`userBubbleHTML`/`typingHTML`; `settings.js` `makeRow`; `user-contacts.js` `createContactRow`/`showAlert`. The `is-selected` chip-toggle pattern is copy-pasted across `settings.js`, `onboarding-world`, `onboarding-ai-existing`, `onboarding-ai-create` (4×).

### 2.3 Server↔client contract (the migration crux)
**Already JSON (browser-fetched)** — no backend change to reuse from React:
`/send_message`, `/regenerate_message`, `/edit_message`, `/load-more-messages`, `/dismiss-draft`, `/transcribe` (chat); `/add-contact`, `/edit-contact/<id>`, `/delete-contact/<id>` (contacts); `/settings/memory`, `/settings/fact/<id>`, `/settings/memory/<id>`, `/settings/memory/forget-all` (settings); `/profile/delete-ai/<id>`.
Note **mixed request bodies**: chat uses `application/json`; contacts/settings/profile use `FormData`. A React data layer should normalize these.

**HTML-only / redirect routes that would need JSON equivalents for a SPA:**
- Page-shell GETs: `/chat`, `/settings`, `/user-settings/contacts`, `/profile`, `/ai-settings/<id>`, the onboarding GETs. (Item ops under them are already JSON.)
- Form-POST-then-redirect: `/login`, `/signup`, `/settings/proactive`, `/profile`, `/upload-profile-image`, `/onboarding/*` POSTs, `/create-checkout-session`, `/change-ai/<id>`.
- Static/marketing/legal + Stripe return pages (`render_template`, no change needed).

**Key nuance:** `/load-more-messages` and `/dismiss-draft` resolve the active AI from `session['ai_id']`, not a request param — so they depend on the cookie session. This *favors Option A* (keep cookie session) and is a gotcha for any stateless-SPA (Option B) path.

### 2.4 Interactivity ranking (React benefit, high→low)
1. **Chat** (`chat.html`+`chat.js`, 1170 lines) — optimistic updates, 6 endpoints, mic/voice lifecycle, and a **duplicated render path** (`draft_card` Jinja macro vs `renderDraftCard` JS) React would unify.
2. **Settings memory list** (`settings.js`) — list-CRUD with inline edit + count reconciliation.
3. **Contacts** (`user-contacts.js`) — table + add/edit modal + delete-confirm + toast.
4. **Onboarding chip/card pickers** — the 4×-duplicated `is-selected` pattern → one shared `<ChipPicker>`/`<RadioCards>`.
5. **ai_settings / profile** — mostly avatar preview + password toggle; lowest.

### 2.5 Auth/session
flask_login **server-side cookie session** (`login_view='auth.login'`, 7-day lifetime, prod `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE=Lax`). Every app route `@login_required` + `current_user`. Session also carries app state: `last_active_ai_id`, `ai_id`, `context_length`. Google OAuth (Authlib) is the alternate login. **No CSRF tokens** (both JS files note "not wired yet"); **no JWT/token endpoint**. → A React SPA can **keep the cookie session**: JSON-ify `/login`+`/signup` (still calling `login_user` to set the cookie) and **add CSRF** (already the pending PROD-2 item). Session-carried state (`ai_id`, `context_length`) stays server-side under Option A.

### 2.6 Static serving
One CSS link in `_base.html` (`url_for('static', 'css/pocket.css')`); fonts via Google CDN; 3 external JS via `url_for('static', …)`; all other page JS inline. **No cache-busting** (no hashed names, no `?v=`, no `SEND_FILE_MAX_AGE_DEFAULT`), **no build step**. A bundler introduces content-hashed filenames (closing the current cache-busting gap) fed via a Vite `manifest.json` → `vite_asset()` helper.

---

## 3. Toolchain options

| Option | What it is | Pros | Cons | Fit |
|---|---|---|---|---|
| **A. Vite + React islands, served by Flask** | Vite builds a bundle Flask serves as a static asset; React mounts into specific `<div id>` mount points inside existing Jinja pages. Keep Flask routing + auth cookie. | Smallest blast radius; strangler-friendly (one island at a time); keep server-rendered auth/SEO shells; no separate deploy. | Manifest wiring between Vite output and Jinja (`vite_asset()` helper); two mental models during transition. | **Recommended** — matches "migrate one surface at a time." |
| **B. Next.js / standalone SPA + Flask JSON API** | React app is its own deployable; Flask becomes a pure JSON API behind it. | Clean separation; modern DX; SSR/streaming available. | Forces API-ifying *all* routes up front; new deploy target + CORS/auth-token rework; biggest, least-reversible step. | Defer — only if we later want a fully decoupled frontend. |
| **C. HTMX/Alpine instead of React** | Stay server-rendered, add lightweight interactivity. | Tiny; no build step; keeps Jinja. | Not React (contradicts the directive); ceiling on complex client state (the chat surface). | Out of scope — noted only as the "don't migrate" baseline. |

**Recommendation: Option A (Vite + React islands).** It honors "stay Jinja for now" literally — most pages remain Jinja, and React is introduced surface-by-surface starting with chat, each behind the existing route. Auth stays cookie-session (no token rework). Reversible per surface.

---

## 4. Migration strategy (strangler, Option A)

**Phase R0 — Toolchain beachhead (no user-visible change).**
- Add `frontend/` with Vite + React + TypeScript; build to `src/static/dist/`.
- Add a `vite_asset(name)` Jinja helper that reads Vite's `manifest.json` (dev: point at the Vite dev server; prod: hashed files → free cache-busting, closes a current gap).
- Convert **one trivial, low-risk island** (e.g. the AI-switcher dropdown or a settings toggle) to prove the mount/build/serve loop end-to-end. Ship it. Everything else stays Jinja.

**Phase R1 — Chat surface (the payoff).**
- Reimplement the message list + composer + draft card + mic/voice as a React island mounting into `chat.html`. This replaces the largest, buggiest imperative JS.
- Keep the exact fetch contracts already defined (`/send_message`, `/regenerate_message`, `/edit_message`, `/load-more-messages`, `/transcribe`, `/dismiss-draft`) — no backend change needed; the contracts are already JSON. This is why chat is the natural first real surface.

**Phase R2 — Settings + onboarding interactivity.**
- Memory list (add/edit/forget/forget-all), proactive form, chip pickers → React. Some settings sub-endpoints are already JSON; the proactive *form* POST would move to a JSON endpoint (small, additive).

**Phase R3 — Remaining page routes.**
- Contacts, ai_settings. Decide per-surface whether they justify React or stay Jinja. Static pages (landing, pricing, legal, auth) likely stay Jinja indefinitely — no reason to React-ify them.

**Contract work (the real cost):** each surface that isn't already JSON-backed needs its route split into (a) a thin HTML shell route and (b) JSON endpoints. §2.3 enumerates exactly which routes need this; the chat surface needs **none**, which is why R1 is cheap relative to its value.

---

## 5. Effort & risk

- **R0:** ~1–2 days (toolchain, helper, one island). Low risk, fully reversible.
- **R1 (chat):** ~1 week. Medium — it's the interactive core, but contracts already exist and are dual-reviewed. Ship behind a feature flag / template swap so we can revert to `chat.js` instantly.
- **R2–R3:** incremental, scoped per surface; each independently shippable.

**Risks:** (1) dual-stack cognitive load during transition — mitigate by migrating fast enough that it's not permanent; (2) auth/CSRF interplay when POSTs move to fetch — CSRF is already a pending pre-launch item (PROD-2), coordinate; (3) build step in CI/deploy — deployment is itself deferred, so fold Vite into whatever deploy target LAUNCH picks.

---

## 6. Recommendation

Approve **Option A, executed as R0→R1 only for now**: stand up the Vite/React island toolchain and migrate the chat surface, since chat is where React pays off most and its JSON contracts already exist. Hold R2–R3 until a feature justifies them. Do not pursue Option B (full SPA) unless we later decide to decouple the frontend deploy. Keep all static/marketing pages on Jinja.

**Next step if approved:** open a `react-frontend` sprint with R0 as the first ticket; keep this doc as the living plan.
