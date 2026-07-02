---
name: session-end
description: End-of-session memory consolidation, reflection, and learning. Promotes findings across the 3-layer memory system (task → sprint → project), proposes learned rules for .claude/rules/, syncs backlog, and archives completed work. Run at the end of a sprint, end of a work session, or whenever consolidation is needed.
---

# /session-end — Session Reflection & Memory Consolidation

_Consolidate what we learned, promote findings upward, propose rules, and leave the project in a clean state for the next session._

---

## When to Run

- **End of sprint** (required) — after all tickets are done/deferred, before marking sprint as completed
- **End of work session** (recommended) — before stopping, especially after substantive work
- **User requests it** — "let's wrap up" or "run /session-end"

**Relationship to the Stop hook:** The Stop hook is enforcement — it blocks stopping if context files aren't updated. `/session-end` is the learning and consolidation step. Run `/session-end` first, then the Stop hook validates the result.

---

## The Workflow

Work through each step in order. Skip steps that don't apply (e.g., no deferred work → skip backlog sync). The goal is thoroughness without busywork.

### Step 1: Session Summary

Read the current sprint.md and active task notepad(s). Write a progress log entry to sprint.md summarizing what was accomplished this session.

**What to capture:**
- Tickets worked on and their current status
- Key milestones reached (investigation complete, implementation merged, tests passing)
- Blockers encountered and how they were resolved (or not)

Keep it factual — 3-5 bullet points, not a narrative.

### Step 2: Promote Findings

Review the sprint's accumulated knowledge and decide what deserves wider visibility.

**From task notepads → sprint.md:**
- Investigation findings that affect other tickets in this sprint
- Design decisions with cross-ticket implications

**From sprint.md → project.md:**
- Architecture changes (new modules, API patterns, tech stack shifts)
- New conventions that emerged during the sprint
- Updated "How to Run" or dependency information

**Heuristic:** If another agent starting a fresh session would need this information to work effectively on ANY ticket in this project, it belongs in project.md. If they'd only need it for THIS sprint's tickets, it stays in sprint.md.

### Step 3: Reflect and Learn

This is the highest-value step. Look for patterns worth turning into persistent rules.

**Sources to review:**
- Task notepad "Corrections & Feedback" sections
- Task notepad "Review Findings" sections
- Sprint.md "Findings" section
- Your own memory of user corrections during the session

**What to look for:**
- Same type of error made 2+ times → systematic pattern
- Reviewers flagged similar issues across tickets → blind spot
- User corrected us on the same thing repeatedly → missed convention
- Assumptions that failed → need for explicit validation

**For each pattern found:** Run the `/learn` reflection process. `/learn` handles the quality filtering — you don't need to duplicate it here. Just identify the candidates and pass them through.

**Output:** 0-3 proposed rules. Don't force rules where there's nothing substantive to learn. One quality rule beats three vague ones.

### Step 4: Sync Backlog

Capture deferred work so it doesn't get lost between sessions.

**Review:**
- Sprint.md "Deferred" section
- Task notepad "Open Questions & Blockers" that won't be resolved this session
- Any items discovered but explicitly out of scope

**For each item:** Add to `.context/backlog.md` with enough context for a future agent to pick it up — source (which ticket/sprint), what the work is, why it was deferred, and suggested next step. Think: "Would a colleague understand this Jira ticket without asking me questions?"

Remove transferred items from sprint.md's Deferred section.

### Step 5: Consolidate & Archive

Keep the context system lean for the next session.

**Consolidate oversized files:**
- If project.md exceeds ~200 lines → tighten language, merge redundant entries
- If sprint.md exceeds ~300 lines → archive resolved findings, compress the progress log
- If any context file is 2x its size cap → consolidate before proceeding

**Archive completed work:**
- Move completed task notepads to `.context/sprints/{sprint}/archive/`
- If the sprint itself is complete (all tickets done/deferred, retrospective written): move entire sprint directory to `.context/sprints/archive/`

**Consolidation strategy:** When a file is too large, ask: "Does this content belong in docs/ instead?" Detailed investigation findings, API documentation, architecture deep-dives — these often belong in `docs/` with a pointer from project.md, not crammed into a 200-line context file.

### Step 6: Report

Tell the user what changed. Keep it concise — a summary, not a log dump.

```
Session wrap-up:

**Progress:** [tickets completed, current status]
**Rules proposed:** [count — titles if any]
**Project.md updated:** [yes/no — what changed]
**Backlog items added:** [count]
**Archived:** [what was cleaned up]

Ready for next session.
```

---

## Integration

- **`/learn`** — Called during Step 3 for each learning candidate. `/learn` handles the full reflection process (root cause analysis, formulation, quality check, user approval, file creation).
- **Stop hook** — Validates that context files were updated. Run `/session-end` before the Stop hook fires to ensure everything is clean.
- **Sprint completion** — If the sprint is done, write the retrospective in sprint.md before running `/session-end`. The retrospective feeds into Step 3's reflection.

---

## Quality Checks

Before finishing `/session-end`, verify:

- [ ] Sprint.md has a progress log entry for this session
- [ ] No findings are stuck in task notepads that should be in sprint.md or project.md
- [ ] Deferred items are in backlog.md (not just sprint.md's Deferred section)
- [ ] Completed notepads are archived
- [ ] No context file is significantly over its size cap
- [ ] project.md is current (architecture, conventions, tech stack all accurate)
