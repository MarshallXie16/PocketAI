# Project: {Project Name}

**Last updated:** {YYYY-MM-DD}
**Size cap:** ~150-200 lines

{3-4 sentence elevator pitch: What are we building? Who uses it? What problem does it solve? Why should we care?}

---

## How to Use This File

This is your mental model of the codebase — the one source of truth for project-level context. Read it first when joining a project. Update it immediately when architecture, tech stack, or key conventions change so future agents have accurate information.

**What belongs here:** Project-level context only — tech stack, directory structure, architectural decisions, and conventions shared across the entire codebase. **What doesn't:** Implementation details and task-specific insights go in `docs/` (see `docs/INDEX.md`). Lessons learned and behavioral rules go in `rules.md`. Sprint-specific work goes in `backlog.md`.

---

## Tech Stack

| Category | Technology | Notes |
|----------|-----------|-------|
| Language/Runtime | — | — |
| Framework/Web | — | — |
| Database | — | — |
| Cache/Queue | — | — |
| Testing | — | — |
| Other key dependencies | — | — |

See `requirements.txt` or equivalent lock file for the complete dependency list. If a dependency is non-obvious or critical to understanding the codebase, add a note explaining why we use it.

---

## Directory Structure

High-level map of the codebase. Not exhaustive — this shows major sections and key locations.

```
.
├── src/                  # Source code
│   ├── handlers/         # Entry points (HTTP routes, CLI commands, etc.)
│   ├── models/           # Data models and schemas
│   ├── services/         # Business logic
│   ├── repositories/     # Data access layer
│   └── utils/            # Helpers and utilities
├── tests/                # Test suite
│   ├── unit/             # Unit tests (no IO)
│   ├── integration/      # Integration tests (with real dependencies)
│   └── conftest.py       # Shared fixtures
├── docs/                 # Documentation (see docs/INDEX.md)
└── scripts/              # Utility scripts (setup, generation, deployment)
```

For the complete directory structure with all files and subdirectories, run `find . -type f | head -50` or a project-specific tree command to get a broader view of the layout.

---

## Architectural Decisions

Major decisions that shape how we work in this codebase. Use ADR (Architecture Decision Record) format. Write one ADR for each significant structural decision.

<!-- Example format:

### ADR-001: Monorepo over multi-repo (2026-03-15)
**Decision:** All code lives in a single repository with clear package boundaries, not split across multiple repos.

**Context:** We serve multiple related services. Multi-repo creates version coordination headaches and makes cross-package changes risky.

**Rationale:** A monorepo with clear package separation allows us to atomically update related code, simplify dependency management, and make refactoring safer. We enforce boundaries via package imports and CI checks, not filesystem separation.

**Consequences:** CI runs on all affected packages when code changes. We need strong discipline on import boundaries. See conventions below for package rules.

---

### ADR-002: Dependency injection over service locator (2026-03-15)
**Decision:** All dependencies are injected via constructor or factory functions, never retrieved from a global registry.

**Context:** Service locators hide dependencies, make tests harder to write, and create implicit coupling.

**Rationale:** Injection makes dependencies explicit and testable. It's easier to mock, easier to trace, and easier for new people to understand what a component needs.

**Consequences:** Constructors may have many parameters. Use factories to manage complexity. Never use global registries for runtime dependencies.

---

### ADR-003: Feature flags over long-lived branches (2026-03-15)
**Decision:** New features are merged to main behind feature flags and toggled on gradually, not kept on long branches.

**Context:** Long-lived branches cause merge conflicts, hide integration issues, and make code review harder. Feature flags let us merge early and test in production.

**Rationale:** Feature flags keep code fresh and enable incremental rollout. We catch integration issues early. We can revert a feature without reverting commits.

**Consequences:** Feature flags must have an expiry date — we delete unused flags every sprint to prevent bloat. See `src/features.py` for the flag registry.

-->

---

## Codebase Conventions

Patterns and practices all code should follow. Conventions are project-wide agreements on style, structure, and approach — they differ from rules (lessons learned from mistakes, captured in `rules.md`).

**When to add a convention:** A convention belongs here if it applies across the codebase and new developers/agents should know it on day one. If a pattern is isolated to one team, module, or emerging, it belongs in `rules.md` instead. Replace placeholder sections with actual conventions from your codebase. Remove sections that don't apply.

### Error handling

Document your standard approach to errors. For example:

<!-- Example:
- Services raise domain exceptions (e.g., NotFoundError, ValidationError) for business logic errors
- Handlers catch domain exceptions and translate them to HTTP responses (404, 422, 500, etc.)
- Never let low-level exceptions (DB, network, OS) bubble up to handlers
- Log exceptions with full context (request_id, user_id, operation name)
-->

### Testing patterns

Document how tests are organized and written. For example:

<!-- Example:
- Unit tests mock all IO and run in `tests/unit/`
- Integration tests use real databases (via fixtures) and run in `tests/integration/`
- Fixtures are defined in `tests/conftest.py` and reused across test files
- Each test should be independent — no test ordering or shared state
-->

### Logging

Document logging conventions. For example:

<!-- Example:
- Use the standard logging module: `logger = logging.getLogger(__name__)`
- Log at INFO for important events, DEBUG for detailed traces
- Always include context (user_id, request_id, operation name)
-->

**Note:** Add sections for any patterns specific to your codebase: state management, dependency injection, caching strategy, API design, database access patterns, async patterns, etc. The goal is to capture patterns that appear across multiple files or services.

---

## How to Run

Quick reference for common development and deployment tasks. Adjust examples for your language, framework, and architecture.

### Development Mode

Run the application locally for development and testing.

<!-- Example: `python app.py` or `npm run dev` or `./gradlew bootRun` -->

If your project has multiple components (backend server, workers, frontend, etc.), show how to run them:

<!-- Example:
- **Backend:** `python app.py` (runs on port 5000)
- **Worker:** `celery -A worker.tasks worker` (in a separate terminal)
- **Frontend:** `npm run dev` (runs on port 3000)
-->

### Testing

Run the test suite locally. Show different test commands for different test types.

<!-- Example:
- **All tests:** `pytest tests/` or `npm test`
- **Unit tests only:** `pytest tests/unit/ -v`
- **Integration tests:** `pytest tests/integration/`
- **Watch mode:** `pytest tests/ --watch` or `npm test -- --watch`
-->

### Linting & Formatting

Check code style and formatting.

<!-- Example:
- **Lint:** `flake8 src/ tests/` or `npm run lint`
- **Format:** `black src/ tests/` or `npm run format`
- **Type check:** `mypy src/`
-->

### Building & Deploying

Build artifacts and deploy to production.

<!-- Example:
- **Build:** `docker build -t myapp:latest .`
- **Deploy:** See `docs/DEPLOYMENT.md` for full pipeline
- **Rollback:** See `docs/DEPLOYMENT.md` for rollback procedures
-->

---

## Documentation References

Refer to these for deeper dives into specific topics:

- **Getting Started & Setup:** `docs/getting-started.md`
- **Architecture & Design:** `docs/architecture.md`
- **API Reference:** `docs/api.md`
- **Database & Data Models:** `docs/database.md`
- **Testing Guide:** `docs/testing.md`
- **Deployment & Operations:** `docs/deployment.md`

See `docs/INDEX.md` for the full documentation index organized by topic.

---

## Known Limitations & Workarounds

Quirks, bugs, or gotchas to watch out for:

<!-- Example entries:
- **Slow migrations on large tables:** Migrations without `batch_size` lock the table. Workaround: use batching for tables >100K rows. See migrations/001_init.py for the pattern.
- **Cache key collisions:** Keys are namespaced by environment (dev/prod) but not by version. Workaround: include version in the key when iterating on cache structures.
- **Vendor library compatibility:** Library X expects v1 of Dependency Y, but we use v2. Workaround: use a compatibility wrapper in `src/utils/compat.py`.
-->

---

## Key Dependencies

| Dependency | Version | Why We Use It |
|-----------|---------|---------------|
| — | — | — |

Include dependencies that are non-obvious or critical to understanding the system. Explain what each dependency does and why we chose it over alternatives. Omit standard libraries or obvious choices.

---

## Environment Variables

Key environment variables needed for development or deployment:

<!-- Example:
- **DATABASE_URL** — Connection string for the main database (required in dev and prod)
- **REDIS_URL** — Redis connection string for caching and queues (optional in dev, required in prod)
- **DEBUG** — Set to `true` in development, `false` in production
- **SECRET_KEY** — Flask/Django secret for session management (generate with `openssl rand -hex 32`)
-->

---

## Common Debugging Patterns

Patterns and techniques for debugging issues in this codebase:

<!-- Example:
- **API hangs:** Check Redis connectivity first (deadlocks often happen there). Then check database connection pool exhaustion.
- **Test flakiness:** Usually race conditions. Use `pytest -p no:cacheprovider --maxfail=1` to isolate and replay.
- **Cache inconsistency:** Clear cache with `redis-cli FLUSHDB` in dev. Check cache key patterns — stale keys often linger.
-->

---

## Maintenance

**Keep it current:** This file is the source of truth for project context. Update it immediately when:
- Architecture changes or you discover a new architectural decision worth documenting
- Tech stack shifts (upgrade major versions, add/remove dependencies)
- Conventions change or new patterns emerge
- Limitations are discovered or workarounds change
- New documentation is created

**Size discipline:** If this file exceeds ~200 lines, consider moving sections to `docs/` and linking from here. Keep this file scannable — agents should be able to read it in 5 minutes.

**Preventing drift:** During code review, if someone's changes violate conventions listed here, call it out. If conventions aren't being followed, it's a sign they need updating or moving to `rules.md` with more emphasis.

---

## Source of Truth

This file is the authoritative project context. Every agent begins here. If you discover something outdated or wrong, update it immediately — stale project context wastes future time.
