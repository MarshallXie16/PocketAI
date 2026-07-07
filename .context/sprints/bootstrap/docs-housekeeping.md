# Task: Docs + housekeeping pass

**Branch:** `docs-housekeeping` (off master)
**Tier:** 1 (docs, dead-code removal, context consolidation — all reversible)
**Started:** 2026-07-06
**Why:** Phases 0–5 complete; maintainer chose a docs/housekeeping pass over launch-prep. Closes the doc gaps found this session and sets up the React migration.

## Scope (6 items)
1. **architecture.md refresh** — add the `settings` blueprint; fix stale route names (`/regenerate`→`/regenerate_message`, `/load_messages`→`/load-more-messages`, add `/dismiss-draft`, `/onboarding/world`); profile no longer owns settings. Note Phase-5 frontend. [me]
2. **frontend.md (NEW)** — design system (`pocket.css` tokens/components), `_base.html` + `_components.html` macros, client JS architecture (chat.js/settings.js/user-contacts.js), the fetch contracts, the hidden+checkbox consent pattern. [me]
3. **Module docstrings** — 10 bare modules: models/{billing,conversation_state,google_user,memory_entry,message,relationship,users}.py, services/integrations/{calendar_service,email_service}.py, utils/utils.py. [delegated → opus subagent]
4. **Backlog consolidation** — bottom half (SEC/BUG/PROD/AI/STRAT/DEBT-1..4) lists Phase 0–4 closed items as if open; collapse to a short "closed by phase" summary, keep only genuinely-open work. [me]
5. **Delete 5 orphaned JS** — ai-settings.js, audio.js, signup.js, script.js, index.js (verified 0 external refs). [me]
6. **INDEX.md** — add frontend.md + react-migration-proposal.md pointers. [me]

## Verification
- 177 pytest still green (orphan JS deletion + docstrings must not break anything).
- Docstrings: each file's docstring is the FIRST statement (above any `from __future__`).
- No route names in architecture.md that don't exist in a blueprint.

## Status
COMPLETE (2026-07-06). Merged to master (`--no-ff`, b118338) + pushed; branch deleted. 177 tests green, ruff clean.
All 6 items done: architecture.md refreshed (route table rebuilt from actual decorators, settings blueprint added); frontend.md written; 10 module docstrings (delegated to opus subagent, verified); backlog consolidated 163→~90 lines (full audit archived to `.context/archive/backlog-audit-2026-07-01.md`); 5 orphan JS deleted (0 refs); INDEX.md updated.

## Decisions
- Archived the full pre-overhaul audit rather than deleting it (historical value: what was fixed + where). Backlog now carries only genuinely-open work.
- Kept SEC-1 (credential rotation) as a maintainer-action note under pre-launch — history was scrubbed but rotation/revocation is a separate manual step.
- Merged straight to master (Tier-1, no behavior change, tests green) without a full dual review — docs/dead-code only; route tables + tokens were built from actual source, not memory.
