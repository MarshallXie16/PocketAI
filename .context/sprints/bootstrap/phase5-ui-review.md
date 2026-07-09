# Task: Phase 5 UI review — bug hunt on the frontend rewiring

**Branch:** `ui-review-fixes` (off master 7df1ee3)
**Tier:** 1 (frontend bug fixes, reversible)
**Started:** 2026-07-08
**Why:** Maintainer spotted UI issues in the merged Phase 5 work; asked for a second-pass review of the previous (opus) session's rewiring + fixes.

## Method
Read every template, all 3 JS modules, pocket.css, and the 6 blueprints that back them; cross-checked every fetch contract against actual route code. Then booted the app on a seeded throwaway sqlite DB (/tmp/ui_review/) and screenshotted 17 pages at desktop+mobile via Playwright. 177 pytest green before starting; all pages render 200.

## CONFIRMED BUGS (fixing in this batch)

1. **Missing default avatar images** (visually confirmed: profile, ai-settings, ob-user, ob-ai-create).
   Templates reference `default_profile_user.png`, `default_profile_ai.png`, `default_profile.png` (6 refs, 5 templates) but `src/static/images/profile_pictures/` only contains `ai_profile_image1.png`/`user_profile_image1.png` (old anime-IP images, unusable). All defaults 404 → invisible avatars (onerror hides) or broken-image icon (ob-ai-create has no onerror). FIX: add on-brand SVG defaults + repoint all 6 refs.

2. **Quiet-hours bar hardcoded** (settings.html): segs are `width:31%`/`4%` regardless of actual times. Seeded 22:00–09:30 renders as 00:00–07:30+23:00–24:00. Never updates on input change. FIX: compute segments in settings.js from the two time inputs (handles overnight wrap), update live.

3. **Pricing "Plusit shows up for you"** — `.plan-line` flex/gap rule is scoped `.teaser-card .plan-line` (landing teaser); the pricing page's `.plan-line` in `.plan.plus` gets nothing → name+tag run together. FIX: unscoped `.plan-line` rule in pocket.css.

4. **Checkout regression on /pricing**: pre-redesign page POSTed `/create-checkout-session` with `lookup_key=premium`; redesigned page links both CTAs to signup → NO way to subscribe. FIX: authed users get the checkout form on "Get Plus" (+ "Start free" → /chat); anonymous keep signup links.

5. **Unstyled native inputs on settings**: quiet-hours `input[type=time]` and `#mem-add-input` are outside `.field` and lack `.input` → raw UA styling (visually confirmed). FIX: add `class="input"`.

6. **"day 0 together"** shown in settings sidebar for new users — chat.html guards `> 0`, settings.html doesn't. FIX: same guard.

7. **profile.py password handling**: clearing the field posts '' → `set_password('')` (empty password accepted, sentinel is `!= '*****'` only). FIX: `if password and password != '*****'`.

## Logged, not fixed here
- Voice selects not visually disabled when voice toggle is off (ai_settings + ob-ai-create) — cosmetic → included if trivial, else DEBT-8.
- chat.js: no date divider inserted for newly sent/prepended messages; `data-voice-enabled` attr unused → DEBT-8 note.
- `pytz.timezone()` raises (never falsy) in onboarding_user validation — unreachable via constrained select; pre-existing.
- INSUFFICIENT_CREDITS toast says "Add more to keep chatting" but there is no credits purchase flow (subscription only) → backlog note beside LAUNCH-4.
- Chat thread reserves space for hover-only `.msg-actions` rows (extra vertical air, esp. mobile where hover never fires) — design tradeoff, noted for the React pass.

## Verified-good (no action)
All chat.js fetch contracts match blueprints (`user_message_id`, `pending_action`, `deleted_ids[1:]`, load-more shape incl. `initiated`/`voice_url`); draft-card Jinja macro ↔ JS renderer in sync; consent hidden+checkbox ordering correct in both forms + both handlers; `voice-enabled` plain checkbox is fine ('voice-enabled' in request.form); contacts CRUD contract matches; regenerate walk-back + welcome-regen path OK; monogram/beta-tag/toggle CSS all present.

## Status
Fixes 1–7 (+ voice-picker dimming) COMMITTED on `ui-review-fixes` (c47f82f). 177 tests green, ruff clean, node --check clean; fixed pages re-screenshot-verified (avatars render, quiet bar correct for 22:00–09:30 and live-updates, pricing header spaced, authed Get Plus posts checkout). Default SVGs needed a .gitignore exemption (profile_pictures/* is ignored).
AWAITING: maintainer's own spotted-issues list — reconcile before merging to master. Dev preview server: /tmp/ui_review/boot.py on :5057 (marshall/password123).
