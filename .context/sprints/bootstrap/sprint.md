---
status: active
started: 2026-07-01
updated: 2026-07-01
---

# Sprint: Bootstrap — Secure & Choose a Direction

Resurrect PocketAI safely and set the overhaul's direction. This sprint does the **Phase 0 security triage** (rotate/purge committed secrets) and confirms the **strategic identity** (§6 of `docs/designs/overhaul-and-repositioning.md`) so later sprints have a north star. It intentionally does **not** touch application architecture yet — stabilization is the next sprint (`stabilize`).

**Sprint status:** `planned` (queued, not started). Flip to `active` when work begins — note the Stop hook will then expect context files to be updated each session.
**Size cap:** ~300 lines.

---

## Acceptance Criteria

- [ ] Exposed credentials rotated/revoked (Google OAuth tokens, Azure + ElevenLabs keys).
- [ ] Committed databases removed from the working tree and purged from history; keep-vs-discard decision recorded.
- [ ] `.gitignore` verified to actually protect `src/instance/`, `src/db/`, `.env`.
- [ ] Strategic direction decided and signed off by the maintainer; recorded in Design Decisions and promoted to `project.md`.
- [ ] Next sprint (`stabilize`) proposed from `backlog.md`.
- [ ] Retrospective written.

---

## Tickets

### BOOT-1
**Title:** Rotate all exposed credentials
**Description:** Revoke/rotate the plaintext Google OAuth tokens in the committed `users.db` and the hardcoded Azure/ElevenLabs keys in `text_to_speech.py`. Audit for any other committed secrets.
**Status:** pending
**Priority:** P0
**Estimate:** 3
**Dependencies:** None
**Notepad:** `.context/sprints/bootstrap/boot-1.md`
**Acceptance Criteria:**
- Google OAuth client secret + affected user tokens rotated/revoked in Google Cloud console.
- Azure + ElevenLabs keys rotated; hardcoded values removed from source.
- No remaining secrets found in a history scan (e.g. `gitleaks`/`trufflehog`).
**Notes:** Backlog SEC-1, BUG-3 (admin password). Tier 4 — requires the maintainer's access to the provider consoles.

### BOOT-2
**Title:** Purge committed databases from repo + history
**Description:** Decide whether to preserve the inherited data (2 users / 125 messages / 17 embeddings) by migrating it into a managed DB, or discard it. Then remove the files from the tree and scrub git history.
**Status:** pending
**Priority:** P0
**Estimate:** 5
**Dependencies:** BOOT-1
**Notepad:** `.context/sprints/bootstrap/boot-2.md`
**Acceptance Criteria:**
- Keep-vs-discard decision recorded in this sprint's Design Decisions.
- `src/instance/users.db`, `src/db/chroma.sqlite3`, and the Chroma index removed from tree (`git rm --cached`) and history (`git filter-repo`/BFG).
- `.gitignore` confirmed effective (fresh clone has no tracked DBs).
**Notes:** Backlog SEC-2. Coordinate with the maintainer before rewriting shared history.

### BOOT-3
**Title:** Confirm the strategic direction
**Description:** Review `docs/designs/overhaul-and-repositioning.md` §6 with the maintainer and choose the product identity: the recommended "companion that actually acts" (assistant↔companion gap), pure companionship, or a niche vertical wedge.
**Status:** pending
**Priority:** P0
**Estimate:** 3
**Dependencies:** None
**Notepad:** `.context/sprints/bootstrap/boot-3.md`
**Acceptance Criteria:**
- A single north-star identity chosen and signed off.
- Decision + rationale recorded below and promoted to `project.md`.
- Track-B backlog items (STRAT-2/3/4) re-scoped to the chosen direction.
**Notes:** Backlog STRAT-1. This is the input to every later Track-B sprint.

---

## Design Decisions

**Decision:** BOOT-3 — Product identity is "a companion that actually acts."
**Tier:** 3 (maintainer signed off 2026-07-01 during plan review)
**Rationale:** Sits in the defensible gap between task assistants (act, no relationship) and companions (relationship, no action); reuses every existing asset. Full overhaul (Phases 0–4) approved. Priorities: bugs > maintainability > pivot features > prod-hardening (deferred). No Fable models (cost). Gemini TTS + episodic memory (adapted from ~/autonomous-agent-research/episodic-memory). Agent-scheduled proactive outreach.
**Alternatives rejected:** pure companion (brutal competition + IP/moderation liabilities), niche-vertical-first (kept as GTM framing: executive-function/ADHD-friendly wedge).
**Reversibility:** positioning/copy reversible; feature work reusable either way.
**Scope:** entire product; roadmap in `docs/designs/overhaul-roadmap.md`.

**Decision:** BOOT-2 — Keep a local backup, then purge committed data + rewrite history.
**Tier:** 4 (maintainer chose the option explicitly; force-push approved at plan approval)
**Rationale:** Repo is PUBLIC; users.db (2 users, plaintext Google OAuth refresh tokens) + Azure/ElevenLabs/Stripe-webhook secrets were in pushed history. Data is ~2 test users, not worth a migration.
**Executed 2026-07-01:** backup at `~/pocketai-secure-backup-2026-07-01/` (users.db, chroma, save.txt ×2, pre-rewrite.bundle). git-filter-repo purged: users.db, src/db/, save.txt ×2, recording.wav, __pycache__; literal key strings scrubbed via --replace-text (Azure `d031f7f7…`, ElevenLabs `db648b64…`, Stripe `whsec_b359014…` — found during history sweep). Force-pushed to origin/master (`df1cad0`). History-wide sweep for sk-/AKIA/AIza/whsec_/pk_live patterns: clean.
**Reversibility:** pre-rewrite.bundle restores everything.
**Scope:** git history, all clones.

**Decision:** BOOT-1 (amended) — Credential rotation is maintainer's call, evidence provided.
**Tier:** 4 (requires maintainer's provider-console access)
**Rationale:** Maintainer questioned necessity; evidence gathered: repo public, keys/tokens verifiably in (now-former) history. Recommendation stands: revoke PocketAI at myaccount.google.com/permissions for the 2 accounts; regenerate Azure/ElevenLabs keys if those accounts still exist. History is now scrubbed, but pre-rewrite clones/scrapes may exist. Not blocking any code work.

## Findings
- Repo confirmed PUBLIC (`gh repo view`: visibility PUBLIC).
- Extra secrets found beyond the audit: hardcoded Stripe webhook signing secret in old app.py history + tracked `__pycache__/*.pyc` containing it. Both scrubbed.
- `.gitignore` had `migrations` ignored (wrong — migrations must be tracked); fixed in the hardened .gitignore.
- gh CLI has two github.com accounts; repo owner is `MarshallXie16` (pushes need `gh auth switch`).

## Progress Log

| Date | Session Summary | Next Steps |
|------|-----------------|------------|
| 2026-07-01 | Sprint scaffolded from the 2026-07-01 audit. Project context, backlog, and overhaul/repositioning design doc created. Sprint is `planned` pending kickoff. | Kick off: start BOOT-1 (credential rotation) and BOOT-3 (direction decision) in parallel; flip status to `active`. |
| 2026-07-01 (2) | Plan approved by maintainer (roadmap: `docs/designs/overhaul-roadmap.md`). BOOT-2 DONE (backup + history purge + force-push; extra Stripe whsec found & scrubbed). BOOT-3 DONE ("companion that actually acts"). BOOT-1 amended: evidence given, rotation = maintainer's call. design.md delivered for Cloud Design. Phase 1 DONE + merged (config, BUG-1..12 + 5 unaudited fixes, deps, logging). Phase 2 code+tests+docs COMPLETE on `phase-2-modularize` (34 tests green, ruff clean, native review passed). | Await codex external review (background) → address findings → merge Phase 2 → Phase 3 (provider-API research brief also running in background at `.context/research/`). |

## Deferred
_(none yet)_

## Retrospective
_(write on completion)_

---

## Completion Checklist
- [ ] Acceptance criteria verified.
- [ ] All tickets `done` or `deferred`.
- [ ] Design decisions recorded (keep-vs-discard, direction).
- [ ] Findings documented.
- [ ] `stabilize` sprint proposed.
- [ ] Retrospective complete.
- [ ] Frontmatter `status: completed` + `updated` set.
