# Documentation Index

**Last updated:** 2026-07-01

Table of contents for `docs/`. Quick mental model lives in `../.context/project.md`; deeper reference lives here.

---

## Architecture & Design

- **[designs/overhaul-and-repositioning.md](designs/overhaul-and-repositioning.md)** — **Start here.** Current-state assessment, the phased overhaul→production plan (Phase 0 security → 1 stabilize → 2 modularize → 3 modernize AI → 4 reposition), and the strategic repositioning brief (assistant↔companion gap).

---

## Project Context (in `.context/`, not `docs/`)

- **[../.context/project.md](../.context/project.md)** — Tech stack, directory map, architecture, how to run, known limitations.
- **[../.context/backlog.md](../.context/backlog.md)** — Prioritized work items (security, bugs, prod-readiness, tech debt, AI modernization, strategic spikes).
- **[../.context/sprints/bootstrap/sprint.md](../.context/sprints/bootstrap/sprint.md)** — First sprint: secure & choose a direction.

---

## To be written (as the overhaul proceeds)

- `deployment.md` — build + deploy pipeline once a target is chosen (Phase 1).
- `architecture.md` — post-modularization system design (Phase 2).
- `api.md` — route/endpoint reference after the blueprint split (Phase 2).

---

**Maintenance:** keep this under ~60 lines; add an entry with a one-line description when you create a doc.
