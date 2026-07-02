# Documentation Index

**Last updated:** 2026-07-01

Table of contents for `docs/`. Quick mental model lives in `../.context/project.md`; deeper reference lives here.

---

## Reference

- **[architecture.md](architecture.md)** — Request flow (including AI-core detail: agent loop, provider adapters, confirmation gate, episodic memory, proactive outreach), directory map with one-line purpose per module, app factory pattern, conventions, how-to recipes (add a route / service / model / tool / provider / model-id / test), known debt (LAUNCH-1..5).

---

## Design

- **[designs/overhaul-roadmap.md](designs/overhaul-roadmap.md)** — Executable overhaul plan: Phases 0–4 (purge → stabilize → modularize → modernize AI → companion features), locked maintainer decisions, git strategy, verification steps, key risks. **Start here for strategic context.**
- **[designs/overhaul-and-repositioning.md](designs/overhaul-and-repositioning.md)** — Full current-state assessment and the strategic repositioning brief (assistant↔companion gap). Original north-star audit document.
- **[designs/design.md](designs/design.md)** — Brand and UI design direction for "a companion that actually acts": color palette, typography, visual principles, component direction, and the build prompt for implementing the new UI.

---

## Project context (in `.context/`, not `docs/`)

- **[../.context/project.md](../.context/project.md)** — Tech stack, directory map, architecture, how to run, known limitations.
- **[../.context/backlog.md](../.context/backlog.md)** — Prioritized work items (LAUNCH-1..5 are pre-deploy requirements; Phase 3–4 items follow).
- **[../.context/research/provider-apis-2026-07.md](../.context/research/provider-apis-2026-07.md)** — Internal research: authoritative LLM provider API shapes for Anthropic, OpenAI (Responses API), and Google Gemini (google-genai SDK); extracted from installed SDK source + official docs (July 2026). Reference before touching `src/providers/`.

---

**Maintenance:** keep this under ~60 lines; add an entry with a one-line description when you create a doc.
