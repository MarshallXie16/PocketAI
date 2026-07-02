# Backlog

**Last updated:** {YYYY-MM-DD}
**Size cap:** ~200 lines

Outstanding work that hasn't been scheduled yet. Use this during sprint planning to decide what to prioritize. Update immediately when you discover bugs, defer items from a sprint, or identify improvements.

---

## How to Use This File

Write each backlog item like a Jira ticket for a colleague (or your future self). Include enough context to understand the problem, why it matters, and how to start investigating — without needing to ask questions. Include any preliminary research or investigation findings to avoid re-doing work. This saves enormous time when it's time to schedule the work.

**When to update:** Add items as you discover them during investigation or code review. Don't batch them up. Update the "Last Updated" date when you make changes.

---

## Features & Improvements

### {Item title}

- **What:** Clear description of the feature or improvement. Include context on why it matters (user value, performance, developer experience, etc.).
- **Where:** File path and line numbers (if applicable)
- **Suggested approach:** (optional) How you'd tackle it
- **Blocks:** (if applicable) What work depends on this

<!-- Example:
### Support sparse responses in API

- **What:** Add query parameter to let clients request only the fields they need. Reduces mobile payload by 50–70% for clients that don't need all data. Users have requested this in support tickets.
- **Where:** `src/handlers/api.py`, serialization in `src/models/serializers.py`
- **Suggested approach:** Add `?fields=id,name,email` parameter. Parse in the handler and pass to serializer. Serializers already support field selection, so this is mostly integration.
- **Blocks:** None

-->

---

## Bugs

Issues found during investigation or code review that aren't being worked on right now.

### {Item title}

- **Where:** File path and line numbers
- **What:** Clear description of the bug. What's broken? What's the impact?
- **Severity:** High/Medium/Low (does it break production? block other work? degrade experience?)
- **Discovered in:** Sprint X, feature Y, or investigation context
- **Suggested fix:** (optional) Direction or approach to fixing it

<!-- Example:
### Empty list returned instead of error on database timeout

- **Where:** `src/models/feed.py:287`
- **What:** `get_related()` returns `[]` when the database times out instead of raising an exception. Errors are masked and callers think the list is empty when actually it's an error condition. Found during performance testing under load.
- **Severity:** Medium — causes silent failures that are hard to debug
- **Discovered in:** Sprint 8, performance investigation
- **Suggested fix:** Catch database timeouts and raise TimeoutError explicitly. Update callers to handle exceptions instead of checking for empty lists.

-->

---

## Deferred Items

Items moved from a recent sprint with source context. Include what blocked them and what needs to happen next.

### {Item title}

- **Source:** Sprint X, TICKET-YYY
- **What:** Clear description of the work
- **Blocker:** What's preventing this from being worked on?
- **Next step:** What needs to happen to unblock?

<!-- Example:
### Refactor database queries for connection pooling

- **Source:** Sprint 8, ARCH-142
- **What:** N+1 queries in the summary serialization reduce performance under load. Investigation identified 6 locations where we prefetch data incorrectly. Estimated fix: 2–3 days.
- **Blocker:** Database pool config PR is in review. Can't safely change connection patterns until that's merged.
- **Next step:** Unblock the pool config PR, then update the affected queries.

-->

---

## Technical Debt

Code improvements that don't impact functionality but should be addressed soon.

### {Item title}

- **Where:** Path and line numbers
- **Issue:** What's wrong?
- **Why it matters:** Impact on maintainability, performance, or developer experience
- **Effort:** Time estimate (e.g., 4 hours, 1–2 days)

<!-- Example:
### Variable naming: `s` → `summary`

- **Where:** `src/models/recap.py:196–220`
- **Issue:** Loop variable `s` is unclear in polymorphic code. Took new engineer 30 minutes to understand what `s` was.
- **Why it matters:** Readability is critical. Future maintainers will struggle without clear names.
- **Effort:** 2 hours

### Redundant database prefetch in serialization path

- **Where:** `src/models/serializers.py:1467–1469`
- **Issue:** `json()` method prefetches related records even when already loaded. Causes unnecessary network round-trip when serializing multiple objects.
- **Why it matters:** Serialization is called in the hot path. Small optimizations compound.
- **Effort:** 4 hours

-->

---

## Future Improvements

Larger opportunities discovered during investigation: optimizations, feature requests, architectural improvements.

### {Item title}

- **Scope:** What would it involve?
- **Value:** Why is it worth doing?
- **Effort:** Time estimate

<!-- Example:
### Batch-prefetch related records to eliminate N+1 queries

- **Scope:** Refactor the data access layer to prefetch records in batches instead of one-at-a-time.
- **Value:** Eliminate 50+ queries in the typical user detail flow. Est. 2–5x speedup for the most common API endpoint.
- **Effort:** 1–2 days

### Concurrent IO via async gathering

- **Scope:** Identify independent IO operations in the serialization pipeline and run them in parallel using `asyncio.gather()`.
- **Value:** Three independent operations (`fetch_data_a`, `fetch_data_b`, `fetch_data_c`) are run sequentially now. Running in parallel would be 3–5x faster.
- **Effort:** 6–8 hours

-->

---

## Maintenance

**Size discipline:** If this file exceeds ~200 lines, consolidate or close completed items more aggressively. A long backlog signals stale items that aren't worth doing.

**Pruning:** During sprint planning, review deferred items. If something has been deferred 2+ sprints without progress, either commit to it next sprint or delete it — it's probably not actually important.

**Effort estimates:** Use hours (h), days (d), or ranges (e.g., 4–6h) to help with sprint planning.

**Blocking items:** If a backlog item blocks active sprint work, escalate immediately. Don't keep it in the backlog — move it to the current sprint.
