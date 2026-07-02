---
name: learn
description: Extract behavioral rules from experience, corrections, and code review findings
---

# /learn — Reflective Learning

_Turn corrections and discoveries into persistent behavioral rules stored in `.claude/rules/`._

---

## What This Does

When you encounter a correction, miss something in review, or discover a pattern worth preserving, `/learn` guides you through structured reflection to extract rules. The goal: distill experience into specific, actionable behavioral guardrails that prevent the same mistake recurring.

---

## Modes (Three Invocation Patterns)

1. **`/learn`** (no args) — Review recent work (task notepad, sprint.md) and propose rules from corrections and discoveries
2. **`/learn "rule text"`** — User provides rule text; you refine it and create the rule file
3. **`/learn --from-ticket TICKET-ID`** — Review a completed ticket's notepad and extract lessons learned

---

## When to Use

**Explicit triggers (user initiates):**
- End of sprint or session (recommend as part of `/session-end`)
- User says "let's learn from this" or "remember this for next time"
- User provides corrective feedback ("do it this way instead")

**Implicit triggers (you propose after):**
- Receiving user correction — fix first, then propose a rule
- Code review catches a systematic pattern (2+ instances)
- Test failure due to a misconception, not a typo
- Making the same error type twice in one session

**Do NOT propose a rule for:**
- One-off typos or formatting issues
- Single-ticket edge cases (unless part of a broader pattern)
- Obvious best practices training data already covers ("write tests," "use type hints")
- Vague feedback without concrete examples ("write better comments")

---

## The Reflection Process

### Step 1: Identify the Learning

Be specific. Describe the concrete incident, correction, or discovery.

**Good examples:**
- "User corrected me: 'Never assume the code does what the docstring says — read the actual implementation.' I had misread a function signature from its docstring instead of checking the real code."
- "I made the same async test mistake twice in one session — first using `create_task` without awaiting, then forgetting to await `gather`. Both caused flaky tests."
- "Code review flagged: 'Always validate token expiry server-side, not just client-side.' This appeared in 3 different PRs."

**Avoid:**
- "I need to be more careful" → Careful about what?
- "There was a mistake" → Which mistake?

### Step 2: Root Cause Analysis

Find the **WHY**, not just the **WHAT**. This is where bad rules die.

**Wrong:** "I forgot to await the async call" → Too shallow.

**Right:** "I forgot to await because [root cause]. The pattern is: [generalized lesson]"

**Example walkthrough:**
- Incident: Forgot to await `asyncio.gather` in tests
- Surface symptom: Called `create_task` without awaiting
- Root cause: Assumed `create_task` and `gather` were equivalent without testing the assumption
- Pattern: I make assumptions about library behavior rather than reading docs or testing
- Proposed rule: "Validate assumptions about library behavior — especially async/concurrency APIs. Read the source or test instead of guessing."

**Guiding questions:**
- Did I make an assumption instead of checking? → Pattern: "Assumption-driven development"
- Did I skip a verification step? → Pattern: "Insufficient validation"
- Did I misunderstand a library or API? → Pattern: "Incomplete API familiarity"
- Did I overlook a requirement or edge case? → Pattern: "Incomplete requirements gathering"

### Step 3: Formulate the Rule

Turn root cause into an actionable, specific rule. Structure:

```
**What:** [Specific action to take or validation to perform]
**Why:** [Brief explanation — 1 sentence]
**When:** [Which scenarios trigger this; be specific about scope]
**Example:** [Concrete before/after or code snippet]
```

**Good rules:**
- "Always validate token expiry server-side, before business logic. Client-side checks are insufficient because client clocks can be wrong or compromised. Applies to ALL protected endpoints. Example: ..."
- "Read the actual implementation before relying on a docstring. Docstrings can be out of sync with the code. Applies when you're unfamiliar with a library, API, or function. Example: Instead of assuming what `asyncio.gather` does based on docs, read the source or test it."

**Bad rules (and why they fail):**
- "Be careful with async code" → Too vague. What specifically?
- "Always test your assumptions" → Obvious from training data. No learned insight.
- "Use asyncio.gather, not create_task" → Too specific. The real rule is about understanding concurrency primitives.
- "In the auth module's refresh endpoint, check token expiry" → Too narrow. Applies to one function in one ticket.

### Step 4: Determine Scope

**Path-scoped** (include `paths:` in frontmatter):
- Domain-specific practices ("JWT auth always validates server-side" → `src/auth/**/*`)
- File-type conventions ("Python modules must have docstrings" → `**/*.py`)
- Use when the rule would be irrelevant in other parts of the codebase

**Unconditional** (no `paths:` key):
- Process rules ("always validate assumptions before planning")
- Architecture principles ("avoid circular dependencies")
- Behavioral guardrails ("when corrected, consider proposing a rule")
- Use when the rule applies everywhere, regardless of domain

**Decision heuristic:** "Does this apply to ALL work, any file, any domain?" → Unconditional. "Does it only matter in [specific domain/file type]?" → Path-scoped.

### Step 5: Check Duplicates + Verify Quality

Search `.claude/rules/` for similar rules. Use grep to search by keywords:

```bash
grep -r "token" .claude/rules/      # what rules exist about tokens?
grep -r "auth" .claude/rules/        # all auth-related rules?
```

If a duplicate exists:
- Same rule, different wording? → Reference the existing rule instead of creating a new one
- New case extends an existing rule? → Propose updating the existing rule with the new example
- Genuinely different? → Create separately (related but distinct rules are OK)

Then verify quality. Answer "yes" to ALL of these or don't propose the rule:

- **Specific?** Would you know exactly what to do when encountering this pattern again?
- **Actionable?** Does it say WHAT to do, not just what to AVOID?
- **Generalizes?** Applies to multiple scenarios, not one exact case?
- **Non-obvious?** Would training data already teach this?
- **Evidence-based?** Tied to an actual incident, correction, or test failure?
- **Scoped correctly?** Not too broad, not too narrow?

If ANY answer is "no," make the fix and move on. The rule will emerge later from a pattern.

### Step 6: Propose and Write

Present the rule clearly to the user:

```
I found a pattern worth learning:

**Rule:** [Specific, actionable title]
**Why:** [Root cause and why it matters — 1-2 sentences]
**Evidence:** [What triggered this — incident or correction]
**Scope:** [When/where this applies]

Should I create this rule in `.claude/rules/`?
```

On approval, create the rule file:

**File naming:**
- Path-scoped: `{domain}-{descriptor}.md` (e.g., `auth-token-validation.md`)
- Unconditional: `universal-{descriptor}.md` (e.g., `universal-assumption-validation.md`)

**File content:**

```markdown
---
paths: ["{glob pattern}"]     # Optional. Omit for unconditional.
tags: ["{domain}"]             # Optional. For discoverability.
added: {YYYY-MM-DD}
source: "{ticket ID, user feedback, code review}"
---
# {Rule Title}

{1–2 paragraph explanation: what to do, why it matters, failure mode.}

## Example

{Code example or concrete scenario showing wrong vs. right.}

## When This Applies

{Specific situations where this rule is relevant.}
```

---

## Integration

- **`/session-end`** calls `/learn` to extract learnings from completed work
- **Ticket completion** includes: "Promote findings to sprint.md or project.md; propose rules if applicable"
- **Stop hook** reminds you to save state and suggests running `/session-end`, which includes `/learn`

---

## Final Principle

**Depth over quantity.** One specific, evidence-based, generalizable rule is worth ten vague "don't do X" rules. Take time during reflection to understand WHY mistakes happen. That understanding is where rules come from.
