# Frontend Architecture

**Current state: Phases 0–5 complete, on `master`.** The UI is server-rendered Flask/Jinja on a hand-rolled design system (`pocket.css`), with vanilla JS for the interactive surfaces. **There is no build step** — no npm, bundler, or `node_modules`. This document covers the client; the server/route side is in [architecture.md](architecture.md). A future migration to React is scoped (not started) in [designs/react-migration-proposal.md](designs/react-migration-proposal.md).

---

## Stack at a glance

| Layer | What | Where |
|-------|------|-------|
| Design system | One hand-authored CSS file: tokens + component classes | `src/static/css/pocket.css` (~950 lines) |
| Layout shell | Base template every page extends | `src/templates/_base.html` |
| Reusable markup | Jinja macros | `src/templates/_components.html` |
| Pages | One template per route, extend `_base.html` | `src/templates/*.html` |
| Interactive JS | 3 vanilla-JS modules (chat, settings, contacts) | `src/static/js/{chat,settings,user-contacts}.js` |
| Fonts | Hanken Grotesk via Google Fonts CDN | `_base.html` `<head>` |

Most pages need no external JS; the interactivity lives in inline `<script>` blocks (avatar preview, password toggle, chip pickers). Only chat, settings, and contacts load an external module.

---

## Design system (`pocket.css`)

### Tokens (`:root`)

Warm, paper-like palette — "bone" page, near-white raised surfaces, a single clay accent. Never introduce ad-hoc hex values; use a token.

| Group | Tokens |
|-------|--------|
| Surfaces | `--bone #EFEDE8` (page), `--surface #FBFAF8` (panels), `--bubble #F1EEE6` (companion bubble), `--white #FFFFFF` |
| Lines | `--line #DAD6CC`, `--line-subtle #EDEAE2`, `--line-dark #35322C` (on ink) |
| Text | `--ink #1A1916`, `--ink-soft #5C564A`, `--ink-panel #2A2620`, `--secondary #797366`, `--muted #A19A8B` |
| Accent | `--clay #C4472B`, `--clay-dark #E8A18C` (on dark surfaces) |
| Radii | `--radius-btn 10px`, `--radius-field 12px`, `--radius-card 14px` |
| Motion | `--ease cubic-bezier(0.2,0.6,0.2,1)`, `--dur 0.18s` |
| Layout | `--page-x 56px` (24px under 720px), `--maxw 1180px` |

**Contrast note:** clay on bone is 4.2:1 (below AA 4.5:1). For small clay text on the page background use the `.beta-tag` pill (clay on white, 4.9:1) rather than `.text-clay` directly on bone.

### Component sections

`pocket.css` is organized top-to-bottom as: Design tokens → Reset/base → Layout helpers → Typography scale (`.type-display/heading/title/body`) → Buttons (`.btn`, `.btn-primary-ink`, `.btn-primary-clay`, `.btn-secondary`, `.btn-tertiary`, `.btn-quiet`) → Fields (`.field`, `.input`) → Choice chips (`.chip`, `.is-selected`) → Toggle (pure-CSS checkbox: `.toggle`/`.toggle-track`, `.toggle-lg`) → Cards (`.card`, `.card-ink`, `.card-selectable`) → Message bubbles (`.bubble-companion`, `.bubble-user`) → Draft→confirm card (`.draft-card`) → Monogram avatar → Site nav header → Flash messages → Footer.

---

## Templates

### `_base.html` — the shell

Every page `{% extends '_base.html' %}`. Blocks it exposes:

| Block | Purpose |
|-------|---------|
| `title` | `<title>` (defaults to the tagline) |
| `head` | Per-page `<style>`/meta (most pages inline their page-specific CSS here) |
| `header` | Site nav (auth-gated via `current_user.is_authenticated`); **chat overrides it empty** for its full-screen shell |
| `flash` | Flash-message stack; **chat overrides it empty** and renders an in-shell toast instead (the base stack would push its 100dvh shell below the fold) |
| `content` | Page body |
| `footer` | Site footer; chat overrides it empty |
| `scripts` | Per-page `<script>` (external module or inline) |

### `_components.html` — macros

Import with `{% from '_components.html' import ... %}`.

| Macro | Renders |
|-------|---------|
| `monogram(name, size=40)` | First-letter circular avatar |
| `companion_bubble()` / `user_bubble()` | Message bubbles (caller supplies the body block) |
| `reached_out_header(name, time)` | "{name} reached out" header for proactive (`initiated`) messages |
| `action_chip(text, meta=None)` | "companion acted" evidence chip |
| `draft_card(pending)` | Email/calendar draft→confirm card; buttons carry `data-draft-action="send\|edit\|dismiss"` |

**Important:** `draft_card` renders the *initial* server-side pending action. When a new draft arrives mid-conversation, `chat.js` `renderDraftCard()` rebuilds the same structure via DOM APIs. The two render paths must stay in sync (a natural consolidation target for the React migration).

---

## Client JS

All three modules are self-invoking IIFEs (`'use strict'`) that bootstrap off a root element's `data-*` attributes and bail if that element is absent — so a module is inert on pages it wasn't meant for. They talk to the server only through the JSON `fetch()` contracts below; escaping is via `textContent`/an `esc()` helper (never `innerHTML` with untrusted text).

| Module | Root | Responsibilities |
|--------|------|------------------|
| `chat.js` (690 lines) | `.chat-app` (`data-selected-model`, `data-ai-name`, `data-settings-url`) | send / regenerate / inline-edit / copy / infinite-scroll load-more / draft-card lifecycle / mic→transcribe / voice playback / AI-switcher dropdown |
| `settings.js` (176) | `#memory-card` (`data-add-url`, `data-forget-all-url`) + chip groups | memory list CRUD (add/edit-in-place/forget/forget-all), check-in + frequency chip pickers writing hidden inputs |
| `user-contacts.js` (153) | contacts table | add/edit modal, delete-confirm modal, row building, toast |

### Fetch contracts (client ↔ server)

Routes are frozen; see [architecture.md](architecture.md) for the blueprint that owns each. Request/response shapes:

| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/send_message` | `{message, modelId}` (JSON) | `{response, voice_url, timestamp, ai_message_id, user_message_id, pending_action}` |
| POST | `/regenerate_message` | `{ai_message_id, user_message, modelId}` | `{response, ai_message_id, deleted_ids, timestamp}` |
| PUT | `/edit_message` | `{message_id, new_content}` | `{success}` |
| POST | `/load-more-messages` | `{current_message_count}` | array of `{id, sender, message, timestamp, voice_url, initiated}` |
| POST | `/dismiss-draft` | — | `{success}` |
| POST | `/transcribe` | multipart `audio` | `{text}` |
| POST/PUT/DELETE | `/settings/memory`, `/settings/fact/<id>`, `/settings/memory/<id>`, `/settings/memory/forget-all` | FormData / — | `{success, ...}` |
| POST/PUT/DELETE | `/add-contact`, `/edit-contact/<id>`, `/delete-contact/<id>` | FormData / — | `{success, contact}` |

**Body-type inconsistency:** chat uses `application/json`; settings/contacts/profile use `FormData`. A React data layer should normalize this.

---

## Key patterns (read before touching these)

- **Consent toggle (hidden + checkbox).** An unchecked HTML checkbox posts nothing, which would make "turn consent off" unreachable. So each consent control pairs a checkbox `value="on"` with a **hidden `value="off"` placed *after* the checkbox** (settings.html, onboarding-world.html). `form_get()` reads the *first* posted value, so a checked box wins ("on") and an unchecked box falls through to the hidden ("off"). The hidden sits after the `.toggle-track` span so the checkbox stays adjacent to it for the pure-CSS toggle. Backend: `settings.update_proactive` / `profile.onboarding_world`.
- **Draft → confirm gate (client mirrors server).** The card's Send/Dismiss buttons send plain chat messages ("Yes — send it." / "Not now…") so the **server-side confirm gate stays authoritative** — the client never executes an action. Dismiss additionally POSTs `/dismiss-draft` first so a stale server draft can't later fire. After each send, the card is reconciled from the response's `pending_action` (render if present, remove if null).
- **Optimistic send + id reconciliation.** `sendMessage` inserts the user bubble immediately, then stamps it with the real `user_message_id` from the response so edit/count work before a refresh. `load-more` counts real `.msg[data-message-id]` rows (not a running integer) to avoid duplicate batches.
- **Timestamps.** DB timestamps are naive UTC; the client parses them as UTC (`parseUTC`) and formats to local time. Date dividers and "reached out" times are relabelled after render.
- **Mic lifecycle.** `getUserMedia` is guarded by a `starting` flag against double-start; any failure after permission stops all tracks so the recording indicator can't stick.

---

## Static serving & known frontend debt

- Assets are served straight from Flask's static handler via `url_for('static', ...)`. **No cache-busting** (no hashed filenames / `?v=`) and **no build step** — a bundler would introduce content-hashing (see the React proposal).
- Several pages carry **inline `<script>`** blocks rather than modules (avatar preview, chip pickers) — a duplicated `is-selected` toggle pattern appears in `settings.js` + three onboarding templates.
- **No CSRF token** in forms/fetch yet (LAUNCH-1 / PROD-2); fetch relies on the same-origin cookie session.
- Legal pages (`privacy-policy.html`, `terms-of-service.html`) may still carry pre-redesign markup — low-priority cleanup.
- 5 orphaned JS files were removed in the docs-housekeeping pass (2026-07-06); the live modules are the three above.
