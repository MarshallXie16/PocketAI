# Rule File Template

This is a template for creating new rule files in `.claude/rules/`. Rules are learned from THIS project's experience, not training data. Each rule is a separate file, making them discoverable via path-scoping and lazy-loaded when relevant.

## How to Use This Template

1. **Create a new file** in `.claude/rules/` with a descriptive name: `{domain}-{descriptor}.md` or `universal-{descriptor}.md`
   - Examples: `auth-token-validation.md`, `api-error-handling.md`, `universal-test-coverage.md`
   - Reason: filenames are searchable; descriptive names help agents find relevant rules via grep.

2. **Fill in the frontmatter** with scope, tags, and source information.
   - `paths`: optional; omit for unconditional rules that apply everywhere.
   - `tags`: optional; for discoverability (e.g., "auth", "security").
   - `added`: date the rule was created.
   - `source`: where the rule came from (e.g., "user feedback on AUTH-003", "code review").

3. **Write the rule content** with: a title, 1–2 paragraph description, an example, and context for when it applies.

4. **Keep it focused.** One rule per file. If you find yourself writing multiple unrelated rules, create separate files.

---

## Template

```markdown
---
paths: ["{glob pattern}"]  # Optional. Omit for unconditional rules.
tags: ["{domain}"]          # Optional. For discoverability.
added: {YYYY-MM-DD}
source: "{ticket, user feedback, code review, etc.}"
---
# {Rule Title}

{1–2 paragraph description: what to do, why it matters, concrete scenario where this would bite you.}

## Example

{Code example showing the wrong way and the right way. Or a concrete scenario.}

## When This Applies

{Specific situations where this rule is relevant. Helps the agent decide if it applies to their current work.}
```

---

## Example: Path-Scoped Rule

```markdown
---
paths: ["src/auth/**/*.ts"]
tags: ["auth", "security"]
added: 2026-03-10
source: "User feedback on AUTH-003"
---
# Always validate token expiry server-side

Client-side expiry checks are insufficient — expired tokens can still reach the server if the client clock is wrong. Always add server-side validation as the primary check, before any business logic.

## Example

```python
# BAD: Client-side only
if token.expiry > now():
    process_request(token)

# GOOD: Server-side validation
def validate_token(token):
    if token.expiry < now():
        raise TokenExpiredError()
    return decode(token)
```

## When This Applies
- Any token validation endpoint (auth, refresh, any protected route)
- Regardless of whether client-side validation exists
```

---

## Example: Unconditional (Universal) Rule

```markdown
---
tags: ["process", "quality"]
added: 2026-03-12
source: "Repeated pattern in TEST-001, TEST-003, TEST-005"
---
# Always validate assumptions before planning

Never assume the code works as written without checking. Read the actual implementation. Test assumptions if skeptical.

## Example

**Wrong way:**
- User says "the endpoint validates tokens" → assume it does → plan implementation
- Later discover the validation was incomplete → rework the plan

**Right way:**
- User says "the endpoint validates tokens" → read the actual code
- Spot a missing server-side check → ask for clarification → plan with full understanding

## When This Applies
- Before starting any implementation (planning phase)
- When working in unfamiliar code
- After receiving requirements from the user (verify, don't assume)
```

---

## Path-Scoped vs. Unconditional Rules

**Use `paths` for:**
- Rules specific to a file, directory, or file type (e.g., "migrations must list columns explicitly")
- Domain-specific practices (e.g., "JWT auth always validates server-side")
- File-type conventions (e.g., "Python modules must have docstrings")

**Omit `paths` for:**
- Process rules ("always write tests", "consult context files before investigating")
- Architecture principles ("avoid circular dependencies")
- Code review criteria ("review for security, performance, conventions")
- Behavioral guardrails ("when corrected, propose a rule")

---

## Naming Convention

- **Path-scoped:** `{domain}-{descriptor}.md` (e.g., `auth-token-validation.md`, `database-migration-columns.md`)
- **Unconditional:** `universal-{descriptor}.md` (e.g., `universal-test-coverage.md`, `universal-assumption-validation.md`)
- **Rationale:** Filenames are searchable. Descriptive names help agents find relevant rules.

---

## Quality Checklist (Before Creating a Rule)

Before creating a rule, verify:

- [ ] **Specific and actionable.** The rule says exactly what to do. "Always validate expiry server-side" ✓. "Be careful with tokens" ✗.
- [ ] **Would I know what to do?** If I encountered this pattern again, would the rule tell me exactly what to do?
- [ ] **Generalizes beyond one case.** Applies to multiple scenarios, not just the one mistake.
- [ ] **Non-obvious.** Not something training data would recommend. Something learned from THIS codebase.
- [ ] **Evidence-based.** Tied to actual tickets, reviews, or corrections. Not speculation.
- [ ] **No duplicates.** Searched `.claude/rules/` for similar rules. This isn't a restatement.

---

## When Rules Are Created

During `/session-end` or `/learn` workflow:
1. Agent identifies a pattern (mistake repeated 2+ times, user correction, code review finding)
2. Agent does root cause analysis
3. Agent drafts a rule using this template
4. Agent searches `.claude/rules/` for duplicates
5. Agent proposes to user: "Should I create a rule for X?"
6. User approves → agent creates new file in `.claude/rules/`

---

## How Rules Are Used

- **At planning start:** Agent searches `.claude/rules/` for relevant rules by filename or domain.
- **At review start:** Agent reads relevant rules again, checks for compliance.
- **Lazy-loading:** Path-scoped rules automatically load when agent opens matching files. Unconditional rules load always.
- **Promotion path:** Over time, frequently-used rules may promote from path-specific to unconditional (or to project.md conventions) as they mature.
