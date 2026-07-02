---
status: planned
started: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
---

# Sprint: {Goal Name}

{3-4 sentence description of what we're building, why, and success criteria. This is the north star for the sprint.}

**Sprint status:** `planned` (queued, not started) | `active` (currently running) | `completed` (all tickets done/deferred, retrospective written).
**Size cap:** ~300 lines.

---

## How To Use This Sprint File

Think of this sprint file as your live project tracker — similar to a Jira board, but with extra space for design decisions and learnings. Each section serves a specific purpose:

- **Tickets:** The actual work units. Each has acceptance criteria, a notepad for investigation, and a status.
- **Design Decisions & Findings:** Key architectural choices and discoveries that should outlive this sprint.
- **Progress Log:** Breadcrumb trail across sessions so you never lose context.
- **Retrospective:** Written at the end to capture what you'd do differently next time.

Update sections as you work (tickets as they progress, decisions when you make them, findings as you discover them). Use the Completion Checklist at the end as a gate before declaring the sprint done.

---

## Acceptance Criteria

What defines a successful sprint? Verify each criterion is truly satisfied before marking the sprint `completed`.

- [ ] **All tickets resolved:** Every ticket is `done` or `deferred` (no `pending` or `in-progress`). Search-and-replace feature fully functional with unit tests passing.
- [ ] **Acceptance criteria met:** Each ticket's acceptance criteria verified. For example, if a ticket requires "zero security warnings in scan," run the scan and confirm.
- [ ] **Design decisions recorded:** Key tradeoffs documented with reasoning and constraints.
- [ ] **Critical findings documented:** Non-obvious discoveries recorded for future reference or promotion to docs.
- [ ] **Deferred items justified:** Out-of-scope work has enough context to pick up later without ramp-up.
- [ ] **Retrospective complete:** Reflections on what went well, what didn't, and lessons for next sprint.
- [ ] **All checklists verified:** Go through each ticket's completion checklist and confirm all items are checked off.

---

## Tickets

Work items for this sprint. Each ticket below is a unit of work with its own acceptance criteria and notepad.

**What constitutes a ticket?** A ticket is a single, well-scoped piece of work — typically 1-8 story points. A feature like "build user authentication" should be split into multiple tickets (e.g., login UI, backend endpoints, session management). If a ticket feels like it could be split into smaller, independent chunks, split it. This keeps tickets focused and prevents bottlenecks.

**Ticket template:**

### {Ticket Slug}

**Title:** {What are we doing?}
**Description:** {What does this ticket do? What problem does it solve? 1-2 sentences.}
**Status:** `pending` | `in-progress` | `done` | `deferred`
**Priority:** P0 (critical path) | P1 (needed this sprint) | P2 (nice-to-have)
**Estimate:** {1, 2, 3, 5, 8, 13} story points
**Dependencies:** {Blocked by other ticket slugs, if any. "None" if independent.}
**Notepad:** `.context/sprints/{sprint-slug}/{ticket-slug}.md`

**Acceptance Criteria:**
- Criterion 1
- Criterion 2
- Criterion 3

**Notes:**
{Key findings, progress updates, or blockers recorded during work. Update as you go. Leave empty if not started.}

**Example ticket structure:**

### SEARCH-001

**Title:** Implement search index builder
**Description:** Build the backend service that indexes documents for full-text search. This is the foundation for the search feature.
**Status:** done
**Priority:** P0
**Estimate:** 5
**Dependencies:** None
**Notepad:** `.context/sprints/search-feature/search-001.md`

**Acceptance Criteria:**
- Index builder ingests all document types (posts, pages, comments)
- Indexing completes in <500ms for 10,000 documents
- Index stored in `.data/search-index.db`
- Unit tests cover edge cases (empty docs, special characters, large files)

**Notes:**
Complete. Tested with real document corpus. Performance baseline established at 320ms for 10k docs.

### SEARCH-002

**Title:** Add search API endpoint
**Description:** Create the HTTP endpoint that clients use to query the search index. Returns ranked results with snippet preview.
**Status:** in-progress
**Priority:** P0
**Estimate:** 3
**Dependencies:** SEARCH-001
**Notepad:** `.context/sprints/search-feature/search-002.md`

**Acceptance Criteria:**
- GET /api/search?q={query} returns JSON results
- Results ranked by relevance (BM25 scoring)
- Snippet preview shows 100 chars of context around match
- Rate limiting enforced (10 req/sec per IP)

**Notes:**
Endpoint logic complete. Pending: pagination for large result sets, rate limiting implementation.

---

## Design Decisions

Key decisions made during this sprint. Structured so future sprints understand the context and tradeoffs.

### {Decision Title}

**Decision:** {What did we decide?}

**Reasoning:** {Why this choice? What problem does it solve? What alternatives did we consider?}

**Constraints & Impact:** {What's the cost? Performance implications? Affects future work? Maintenance burden?}

**Example:**

### Use Redis for search result caching

**Decision:** Cache search results in Redis with 1-hour TTL rather than in-process memory.

**Reasoning:** Search queries are expensive (full-text scan). Caching prevents redundant index scans. Redis allows cache sharing across multiple API instances if we scale horizontally later. In-process memory would not persist across instances.

**Constraints & Impact:** Adds Redis dependency. Small latency overhead (~5ms) for cache lookup. Requires cache invalidation on document updates. Memory cost ~200MB for 100k cached results, acceptable for our scale.

---

## Findings

Key discoveries during this sprint worth preserving. These may be promoted to `project.md`, `rules.md`, or documentation.

### {Finding Title}

**What was found:** {What did we discover?}

**Where:** {File path, line numbers, method names. Be specific.}

**Why it matters:** {What impact does this have? Is it a bug, anti-pattern, optimization opportunity, or constraint we need to know?}

**Action needed:** {Should this be fixed, documented, refactored, or deferred? Who should know about this?}

**Example:**

### Special characters in queries cause index corruption

**What was found:** Queries containing regex metacharacters (e.g., `*`, `+`, `(`, `)`) are not escaped before being passed to the index builder, causing the index to corrupt on the next write.

**Where:** `search/indexer.py`, line 87 in the `add_document()` method. The query string is concatenated directly into the SQLite query without escaping.

**Why it matters:** Users will corrupt the search index by accident when searching for common punctuation (e.g., "C++" or "file(1).txt"). This breaks search for everyone until the index is rebuilt.

**Action needed:** Escape user input using parameterized queries (SQLite binding). Add regression test for special characters. Promote this as a codebase rule: "Never concatenate user input into SQL queries."

---

## Progress Log

Session-by-session record of accomplishments and next steps. Update before context compaction. The most recent entry tells you exactly where to resume.

| Date | Session Summary | Next Steps |
|------|-----------------|------------|
| 2026-03-18 | SEARCH-001 investigation complete. Designed 3-level index structure. Performance baseline established at 320ms/10k docs. Ready to implement. | Begin SEARCH-001 implementation. Start with the indexer CLI, then add document ingestion. |
| | | |

---

## Deferred

Items discovered but out of scope for this sprint. Include enough context so a future sprint can pick up without ramp-up—think of this as a mini ticket for a colleague.

### {Deferred Item Title}

**What:** {What's the work item?}

**Why deferred:** {Why didn't we do it now?}

**Context needed to unblock:** {What questions need answering? What dependencies are blocking?}

**Estimated effort:** {Story points to tackle it later.}

**Example:**

### Add fuzzy search support

**What:** Allow queries with typos to match results (e.g., "serch" matches "search").

**Why deferred:** Requires implementing Levenshtein distance scoring. Adds complexity and ~20% query latency overhead. Deferred to next sprint pending user feedback on demand.

**Context needed to unblock:** Is fuzzy matching worth the latency cost? Check user support tickets for typo-related complaints. Benchmark performance with Levenshtein implementation.

**Estimated effort:** 5 points.

---

## Retrospective

Written upon sprint completion. Use this to capture what you'd do differently and what patterns should become rules.

### What went well?

{Be specific. What decisions paid off? What investigation prevented rework? What assumptions held up?}

Example: "Upfront investigation of special characters prevented two refactors. Discovered the escaping issue early, before it hit users."

### What didn't?

{What took longer than expected? What assumptions failed? Where did we get stuck?}

Example: "Initial estimate for SEARCH-002 was 3 points but took 5 days. Underestimated complexity of pagination logic."

### Patterns to codify as rules

{What lessons should we apply to future sprints? Should this become a convention in the project?}

Example: "Always escape user input with parameterized queries — never concatenate. This should be in project.md as a non-negotiable rule."

### How would we do this differently?

{If we started this sprint over, what would we change? What would you do first?}

Example: "Would split SEARCH-002 into two tickets: API endpoint (3 pts) and pagination (3 pts). Single ticket masked the complexity."

---

## Maintenance

**When to clean up this file:** Once the sprint is marked `completed`, archive the Tickets, Design Decisions, and Findings sections to a dated archive file (e.g., `archive/sprint-search-feature-2026-03.md`) to keep the active sprint lean. Keep the retrospective here; it's reference material.

**How to prevent drift:** Update this file as you work. Don't batch updates until the end—findings and decisions shift as you go, and batching means forgetting important context. Aim for this file to always reflect current state.

---

## Completion Checklist

Sprint is complete when ALL items below are checked off. Walk through each item, verify it's truly satisfied, and check it off. Do NOT bulk-check without verification.

- [ ] **Acceptance criteria verified:** Re-read the Acceptance Criteria section at the top. For each criterion, verify it's met. For example, if a criterion is "search feature fully functional with unit tests passing," run the test suite and confirm all tests pass. Check this off only if you've actually verified the criterion, not just assumed.

- [ ] **All tickets resolved:** Every ticket marked `done` or `deferred` (no `pending` or `in-progress` remain). Go through the Tickets section, count the statuses, confirm none are ambiguous.

- [ ] **All ticket acceptance criteria met:** For each `done` ticket, re-read its acceptance criteria and verify each one. If a criterion says "zero security warnings," run the security scan. If it says "tests passing," run the tests. Document any failures.

- [ ] **Design decisions recorded:** Every major design choice made during the sprint is documented in the Design Decisions section with decision, reasoning, and constraints. Confirm nothing was skipped.

- [ ] **Findings documented:** Any non-obvious discoveries (bugs, patterns, constraints) are recorded in the Findings section with specificity (file path, line numbers, impact). Confirm all findings are structured (not one-liners).

- [ ] **Deferred items justified:** Each deferred item has context, blockers, and estimated effort. Confirm a colleague could pick it up without asking questions.

- [ ] **Retrospective complete:** All four subsections answered: what went well, what didn't, patterns to codify, how we'd do it differently. Confirm the retrospective is specific (not vague platitudes).

- [ ] **All ticket notepads archived:** Completed ticket notepads moved to `archive/tasks/` or `archive/sprints/{sprint-slug}/`. Confirm the `.context/sprints/{sprint-slug}/` directory is clean.

- [ ] **Progress log current:** Most recent session entry summarizes sprint completion. Confirm it tells the next person/sprint what was accomplished and what comes next.

- [ ] **Status updated:** Frontmatter `status: completed` and `updated: {YYYY-MM-DD}` changed. Confirm it's saved.

Once all items are checked, the sprint is officially complete.