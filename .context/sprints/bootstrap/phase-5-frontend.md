# Task Notepad — Phase 5: Frontend Overhaul (Claude Design integration)

**Ticket:** task #9 · **Branch:** `phase-5-frontend` · **Started:** 2026-07-02
**Design source:** ~/Downloads/pocket-ai-design (canvas export) → extracted to `docs/designs/reference/*.html` (9 screens: landing, chat, chat-mobile, onboarding 1-3, settings, pricing, component-sheet).

## Design system (from component-sheet.html — the source of truth)
Palette: bone #EFEDE8 (page), surface #FBFAF8, bubble #F1EEE6, lines #DAD6CC/#EDEAE2, ink #1A1916, secondary #797366, muted #A19A8B, clay #C4472B (accent), clay-on-dark #E8A18C. Type: Hanken Grotesk ONLY (Google Fonts) — display 58/700/-0.032em, heading 36, title 20, body 15/1.55, label 13.5/600, caption 12/600. Radius 10px buttons/12-14px cards; bubbles companion 4/16/16/16 fill #F1EEE6, user 16/4/16/16 ink. Focus: 2px ink outline offset 2. Monogram avatar = first letter on clay circle (64/40/30). Reached-out header: clay dot + "Mira reached out — 7:42 AM". Draft card: To/Subject header, body preview, [Send it][Edit first][Not now], caption "Nothing sends without your okay."

## Contract for delegated page agents (MUST preserve)
- Endpoints (url_for): pages.home/pricing/privacy_policy/terms_of_service, auth.login/signup/logout + google routes, chat.chat/send_message/regenerate_message/edit_message/load_more_messages/transcribe, ai.ai_settings/change_ai/delete_ai/onboarding_ai(+existing/create), profile.profile/onboarding_user, contacts.*, billing.*, settings routes NEW (below).
- JS fetch paths (hardcoded): /send_message {message, modelId} → {response, voice_url, timestamp, ai_message_id}; /regenerate_message; /edit_message; /load-more-messages; /transcribe (multipart 'audio') → {text}; contacts CRUD.
- Form fields: login(username,password); signup(username,email,password,confirm-password); onboarding_user(username,timezone,messages,profile-image); ai create/settings(ai-name,ai-model,ai-prompt,ai-description,memory-chunk-size,conversation-mode,voice-enabled,voice-id,voice-model,profile-image).
- Template context: chat.html gets ai_model, messages (msg.sender/message/timestamp/voice_url/initiated), + NEW days_together, pending_action.

## New backend (this phase, mine)
- `UserSettings.paused` Boolean (pause everything ≠ losing consent; design: "nothing is deleted"). Tick + delivery skip paused users.
- Blueprint `settings` (new file or extend profile): 
  - GET /settings — renders settings page (context: settings, memories=MemoryEntry list, facts=KeyFact list, google_linked, days_together).
  - POST /settings/proactive — daily_checkin_time ('HH:MM'|'none'), quiet_start, quiet_end, frequency ('low'|'med'|'high' → max_proactive_per_day 1/2/4), paused (checkbox).
  - POST /settings/memory — add user-provided fact (KeyFact, fact_type='preference', source='user').
  - PUT /settings/fact/<id> — edit KeyFact content (ownership).
  - DELETE /settings/memory/<id> (MemoryEntry) + DELETE /settings/fact/<id> (KeyFact) — 'forget'.
  - POST /settings/memory/forget-all — delete all MemoryEntry+KeyFact for (user, active ai).
- GET/POST /onboarding/world (ai blueprint or profile): consent step — proactive consent toggle (sets proactive_consent_at), daily_checkin_time chips, quiet hours; Google connect button → existing auth.link_google. On consent+google-linked → calendar_experiment=True.
- Chat context: days_together (RelationshipState), pending_action (ConversationState) for the draft card. Draft card buttons SEND normal chat messages ("Yes — send it." / "Not now.") → preserves the server-side confirm gate; no new endpoint.

## Decisions
**Decision:** Google-scope toggles in the consent design (read calendar / create events / draft emails) render as informational (fixed on when linked); "send email without asking" renders permanently OFF.
**Tier:** 2. **Rationale:** backend has no per-scope enforcement (single OAuth grant) and the confirm gate architecturally prevents unconfirmed sends — honest UI over fake toggles. **Reversibility:** add real scope prefs later. **Scope:** onboarding-3 + settings templates.

**Decision:** "Pause everything" = new `UserSettings.paused` flag, not clearing proactive_consent_at.
**Tier:** 2. **Rationale:** design promises "nothing is deleted"; consent date is an audit fact. **Scope:** users.py, proactive_service, settings routes.

**Decision:** Draft→confirm card buttons send plain chat messages instead of hitting a new confirm endpoint.
**Tier:** 2. **Rationale:** the Phase-3 security gate REQUIRES a genuine user message after the draft; buttons that literally send one keep a single code path and the gate intact. **Scope:** chat template/js.

## Plan
1. (me) Backend: paused flag + settings blueprint + onboarding/world + chat context. Tests.
2. (agent A, opus) Foundation: base.html + tokens.css + _components macros from component-sheet → landing + pricing + auth pages restyle.
3. (agents B+C parallel, opus) B: chat desktop/mobile + chat JS (mic, chips, initiated, draft card, voice). C: onboarding 1-3 + settings + profile/ai-settings restyle.
4. Reviews (native + codex), suite green, merge.

## Status: IN PROGRESS
