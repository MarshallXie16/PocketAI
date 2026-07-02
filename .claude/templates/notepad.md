---
status: in-progress
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
sprint: {sprint-slug}
---

# Task: {Ticket Title}

This notepad records your investigation findings, decisions, and implementation progress for a single ticket. It persists through context loss (e.g., compactions) and session handoffs. When you resume work, this document tells you exactly where we left off.

For ad-hoc tasks (i.e., not part of a sprint), omit the `sprint` field in the frontmatter.

**Size cap:** ~300 lines during active work. Archive completed notepads to `archive/tasks/` or `archive/sprints/{sprint-slug}/` upon task completion to keep the working directory lean.

---

## How To Use This Notepad

Think of this notepad as your insurance policy against context loss. Anything not written here can be forgotten. It's a living scratchpad for a single task — investigation findings, decisions, implementation progress, blockers. The **Current Status** section is the TL;DR: a fresh session should be able to read just that section and know exactly what's happening, what's done, and what comes next.

**Possible status values in frontmatter:** `in-progress`, `blocked`, `done`, `archived`. Use `blocked` when a blocker prevents forward progress and you've exhausted what you can do alone.

**When to update:** After major milestones (investigation phase done, implementation started, blocker discovered), before context compaction, and whenever you find something worth preserving. Don't wait until the end of the session—update as you go.

---

## Objective

What are we building or fixing, why does it matter, and what does done look like? This section is the canonical reference for what "done" means.

**Task:** {What are we building or fixing?}

**Why:** {Why does this matter? What problem does it solve?}

**Acceptance Criteria:**
- {Criterion 1}
- {Criterion 2}
- {Criterion 3}

**Example:**

**Task:** Implement user authentication system (login, signup, session management).

**Why:** The API is currently public. We need to restrict access to authenticated users and track who is using the system.

**Acceptance Criteria:**
- Users can sign up with email/password and receive confirmation email
- Users can log in with correct credentials; incorrect credentials show error
- Logged-in users receive session token valid for 7 days
- Session tokens validated on all protected endpoints
- Logout clears session token
- Password reset flow works end-to-end

---

## Current Status

**This is the TL;DR section for session recovery.** When you resume after context loss, read THIS section and the Objective above. You should know exactly where you are and what to do next.

Update this section at major milestones (before context compaction, after completing a phase, when blockers arise). Be specific—"60% done" is vague; "Login API complete, pending password reset" is actionable.

**Phase:** {Investigation | Planning | Implementation | Review | Testing | Done}

**Accomplished:**
- {What have we done so far? Be specific—list completed items, not just "worked on stuff"}

**Key Findings:**
- {What did we discover? Unexpected behaviors, blockers, constraints, opportunities?}

**Open Questions:**
- {What's blocking us? What needs clarification?}

**Next Steps:**
{Numbered list of concrete actions. Specific enough that a fresh session knows exactly where to start.}

**Example:**

**Phase:** Implementation (70% complete)

**Accomplished:**
- Login endpoint implemented with bcrypt password hashing
- Session token generation with expiry logic (7 days)
- Database schema for users and sessions created and migrated
- Login and session validation tests passing (12/12)

**Key Findings:**
- Discovered that password reset requires sending emails; will need SMTP service configuration
- Session token validation on protected endpoints not yet added (blocking signup completion)
- Performance: login takes ~200ms (2 DB queries + password hash), acceptable

**Open Questions:**
- Should password reset tokens be time-limited (e.g., 1 hour)? Needs product decision.
- SMTP service: should we use SendGrid or build simple in-memory email for testing?

**Next Steps:**
1. Add session token validation to protected endpoints (1 hour)
2. Implement password reset flow with email (depends on SMTP decision)
3. Test full signup → login → protected endpoint flow end-to-end
4. Code review and then testing phase

---

## Investigation Findings

Record what you've discovered while exploring the codebase. Structure however makes sense for your investigation—subsections, tables, code blocks, call graphs, whatever helps capture the specificity.

### File Paths & Method Locations

Key files and entry points related to this task:

| File | Method/Class | Lines | Purpose |
|------|--------------|-------|---------|
| | | | |

### Call Chains & Dependencies

How are the relevant methods/classes connected? Use diagrams if helpful.

### Patterns & Edge Cases

Significant patterns, surprising behaviors, or edge cases you found:

- {Pattern or edge case description}
- {Another finding}

---

## Implementation Plan

High-level plan for how to implement the ticket. Written during planning phase, informed by investigation findings. Ordered and specific enough to guide implementation.

1. {First major step—be specific (not just "implement auth")}
   - {Substep}
   - {Substep}

2. {Second major step}
   - {Substep}
   - {Substep}

---

## Key Decisions

Decisions made during this ticket. Structured as subsections so the reasoning and impact are clear.

### {Decision Title}

**What was decided:** {What choice did we make?}

**Why:** {Rationale. What problem does it solve? What alternatives did we consider?}

**Impact:** {What's the cost or benefit? Performance, complexity, maintenance burden, future constraints?}

---

## Delegation Log

Track work handed off to subagents. Record what was delegated, status, and any key findings.

| Date | Task | Status | Findings |
|------|------|--------|----------|
| | | | |

---

## Open Questions & Blockers

Items that need resolution. Include context on what's unclear and what's needed to move forward.

- {Blocker or open question}
- {Another blocker}

---

## Review Findings

Feedback from code review or validation during implementation. Record the feedback, how you addressed it, and status.

- **Feedback:** {What feedback was given?}
  **Fix:** {How did you address it?}
  **Status:** {✅ Done | ⏳ In Progress | ❌ Deferred}

---

## Corrections & Feedback

User corrections or feedback received during this ticket. These are potential inputs for the `/learn` skill — patterns worth turning into persistent rules in `.claude/rules/`.

Record what was corrected, what you did wrong, and what the correct approach is. The `/learn` skill reads this section to identify learnings worth preserving.

- **Correction:** {What the user corrected or what you discovered was wrong}
  **Root cause:** {Why did this happen? What assumption failed?}
  **Correct approach:** {What should you do instead?}

---

## Session Log

Continuity across sessions. Update this BEFORE context compaction. The most recent entry tells you exactly where to resume without re-reading the entire notepad.

| Date | What Happened | Next Steps |
|------|---------------|------------|
| 2026-03-18 | Completed investigation of auth requirements. Mapped 8 files, 14 related methods. Identified 3 decision points (password hashing strategy, session token format, email service). Ready for planning. | Begin planning phase. Research bcrypt vs. argon2 for password hashing. Decide on SMTP approach (real service vs. test mock). |
| | | |

---

## Completion Checklist

Before marking this ticket done, walk through each item below and verify it's truly satisfied. Check items off only after verifying; do NOT bulk-check without verification.

**Objective verification:**
- [ ] **Reread acceptance criteria:** Go back to the Objective section. Reread each acceptance criterion.
- [ ] **Verify each criterion met:** For each criterion, verify it's actually satisfied. Don't assume. If a criterion says "login works with correct credentials," test it. If it says "password reset email sent," trace through the code or run it manually. Record here which tests you ran or which code you verified.
- [ ] **Note any unmet criteria:** If any criterion is unmet, list what's missing and whether it's a blocker or can be deferred.

**Implementation verification:**
- [ ] **Investigation complete:** All code paths explored; no gaps in understanding. You understand the system well enough to review code and explain it.
- [ ] **Implementation matches plan:** All steps in the Implementation Plan are done. If you deviated, document why.
- [ ] **All tests passing:** Unit, integration, and manual tests pass. Run the full test suite and confirm.
- [ ] **Documentation updated:** Code comments, docstrings, or external docs reflect your changes. If you changed a public API, is it documented?
- [ ] **Review feedback addressed:** All reviewer comments resolved or explicitly deferred. No outstanding feedback.

**Finalization:**
- [ ] **Findings promoted:** Critical bugs, patterns, or insights documented for future reference or captured in project docs.
- [ ] **Notepad archived:** This notepad moved to `archive/tasks/` or `archive/sprints/{sprint-slug}/` upon completion.
- [ ] **Status updated:** Frontmatter `status: done` and `updated: {YYYY-MM-DD}` changed.

Once all items are checked, the ticket is officially complete.

---

## Maintenance

**When to clean up:** Upon task completion, archive this notepad to `archive/tasks/` or `archive/sprints/{sprint-slug}/{ticket-slug}.md`. This keeps the active working directory lean and preserves a historical record.

**How to prevent drift:** Update this notepad as you work, not at the end. After each major milestone or discovery, spend 2 minutes updating Current Status. This prevents context loss and keeps the notepad accurate. Stale notepads are worse than no notes.

**Size management:** If this notepad exceeds ~300 lines during active work, it's a sign to consolidate Investigation Findings or promote learnings to project docs. Archive completed sections to the historical record.