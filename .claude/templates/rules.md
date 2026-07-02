# Rules & Lessons Learned

**Last updated:** {YYYY-MM-DD}
**Size cap:** ~100-150 lines

This file captures behavioral rules discovered through experience in this codebase. Rules are different from conventions (which appear in `project.md`). Rules are guardrails learned from mistakes, non-obvious gotchas, and user feedback — they evolve as the codebase matures.

---

## How to Use This File

When you discover a lesson worth preserving — a bug caused by violating a pattern, user feedback, a gotcha that surprised you, or a decision that guides how you work — propose it as a rule here. Include: what to do, why it matters (briefly), and a concrete scenario.

**Relationship to other files:** Conventions are rules that appear in 3+ tickets and are fundamental enough to know on day one (those go in `project.md`). Principles deeper than behavioral rules belong in `CLAUDE.md`. Implementation details belong in docs.

**Tag reference:** Use tags to categorize rules. Choose from: `[architecture]`, `[database]`, `[testing]`, `[error-handling]`, `[performance]`, `[async]`, `[api]`, `[security]`, `[process]`. Create new tags as needed.

---

## Active Rules

<!-- Example rule entries:

### [database] Always check for cascading deletes before removing parent records
**Added:** 2026-03-10 | **Source:** Data loss bug in feature X
When a parent record is deleted, the database may cascade and delete related child records. You must verify the foreign key relationships in the schema first. If you're unsure whether deletion will cascade, ask the DBA or run a test migration in staging. This prevents accidental data loss.

### [testing] Mock at the boundary, not the implementation
**Added:** 2026-02-28 | **Source:** Brittle tests in refactor
Mock external dependencies (HTTP clients, databases, message queues) at the module boundary, not internal functions. Mocking internal functions makes tests brittle — they break when you refactor internals even if behavior stays the same. Example: mock `requests.get()`, not `my_service.fetch_data()`.

### [performance] Feature flags must have an expiry date — stale flags become tech debt
**Added:** 2026-02-15 | **Source:** Code review feedback
Every feature flag needs a target removal date. If a flag is older than 2 sprints and the feature is stable, delete it. Stale flags accumulate and turn into unmaintainable cruft. During sprint planning, audit flags that are older than expected and mark them for removal or decide to keep them permanently.

-->
---

## Maintenance

**Promotion to conventions:** When a rule appears consistently across multiple tickets or becomes fundamental knowledge, promote it to `project.md` as a convention. This signals that all new agents should know it on day one.

**Retiring rules:** If a rule is no longer relevant (because a pattern was automated, the codebase evolved, or the lesson no longer applies), delete it. No need to archive — git history preserves it.

**Consolidation:** If you notice similar rules with the same underlying lesson, merge them into a single rule with a broader title.

**Size discipline:** If this file exceeds ~150 lines, review for stale rules and consider promoting mature rules to conventions. Rules should remain active and relevant.