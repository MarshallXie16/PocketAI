# Documentation Index

**Last updated:** {YYYY-MM-DD}

This is the table of contents for the `docs/` directory. Use it to find documentation on a specific topic. Organized by category so you can scan quickly.

---

## How to Use This File

This index is your gateway to deeper documentation. `project.md` is your quick-reference mental model (agent-optimized, ~200 lines). This index and the `docs/` directory contain the reference library (detailed, human-readable). When `project.md` says "see docs/ for details," come here to find the right doc.

---

## Getting Started

- **[README.md](../README.md)** — Project overview, installation, quick start.
- **[setup.md](setup.md)** — Local development environment setup, dependencies, common setup issues.
- **[contributing.md](contributing.md)** — How to contribute: code style, pull request process, code review guidelines.
- **[changelog.md](changelog.md)** — Major changes, releases, and notable updates. Helps you understand what's new and what changed.

---

## Architecture & Design

- **[architecture.md](architecture.md)** — System design overview, major components, data flow, key architectural decisions.
- **[design-patterns.md](design-patterns.md)** — Common patterns used in this codebase: dependency injection, error handling, async patterns, etc.

---

## API Reference

- **[api.md](api.md)** — REST API endpoints, request/response schemas, status codes, error formats.
- **[api-conventions.md](api-conventions.md)** — API design patterns: URL structure, naming conventions, pagination, versioning.

---

## Database & Data Models

- **[database.md](database.md)** — Database schema overview, how to run migrations, query performance tips.
- **[data-models.md](data-models.md)** — Core entity models, their relationships, serialization, and usage examples.

---

## Testing

- **[testing.md](testing.md)** — How to write tests, test organization, fixtures, mocking strategies.
- **[testing-checklist.md](testing-checklist.md)** — Checklist for verifying test coverage before merging.

---

## Deployment & Operations

- **[deployment.md](deployment.md)** — Build, test, and deployment pipeline. Environment setup and configuration.
- **[monitoring.md](monitoring.md)** — Logging, metrics collection, alerts, and how to debug production issues.
- **[troubleshooting.md](troubleshooting.md)** — Common issues and how to resolve them.

---

## Maintenance

**Adding a new doc:** Create the file in `docs/`, add an entry to this index under the appropriate category with a one-line description. Update "Last Updated" date.

**Renaming or moving a doc:** Update all links in this index. Check `project.md` and other docs for any cross-references.

**Removing a doc:** Delete the entry from this index. Search for any links to the deleted doc in other files and update them.

**Keeping descriptions current:** If a doc's content drifts from its description here, update the description immediately. The index is a contract — readers depend on accurate descriptions to know what they'll find.

**Anti-pattern:** Don't let the index grow past ~60 lines. If it does, restructure into subcategories or consolidate related docs. A massive index defeats the purpose of having one.
