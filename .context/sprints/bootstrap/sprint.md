---
status: planned
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
_(record BOOT-2 keep-vs-discard and BOOT-3 direction here as they're made)_

## Findings
_(record discoveries here)_

## Progress Log

| Date | Session Summary | Next Steps |
|------|-----------------|------------|
| 2026-07-01 | Sprint scaffolded from the 2026-07-01 audit. Project context, backlog, and overhaul/repositioning design doc created. Sprint is `planned` pending kickoff. | Kick off: start BOOT-1 (credential rotation) and BOOT-3 (direction decision) in parallel; flip status to `active`. |

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
