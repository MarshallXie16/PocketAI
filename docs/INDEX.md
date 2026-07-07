# Documentation Index

**Last updated:** 2026-07-06

Table of contents for `docs/`. Quick mental model lives in `../.context/project.md`; deeper reference lives here.

---

## Reference

- **[architecture.md](architecture.md)** — **Backend/server** architecture: request flow (agent loop, provider adapters, confirmation gate, episodic memory, proactive outreach), the blueprint route table, directory map with one-line purpose per module, app factory pattern, conventions, how-to recipes (add a route / service / model / tool / provider / model-id / test), known debt.
- **[frontend.md](frontend.md)** — **Client** architecture: the `pocket.css` design system (tokens + components), `_base.html`/`_components.html`, the three vanilla-JS modules, the client↔server fetch contracts, and key patterns (consent hidden+checkbox, draft→confirm mirroring, optimistic send, mic lifecycle). No build step.

---

## Design

- **[designs/overhaul-roadmap.md](designs/overhaul-roadmap.md)** — Executable overhaul plan: Phases 0–4 (purge → stabilize → modularize → modernize AI → companion features), locked maintainer decisions, git strategy, verification steps, key risks. **Start here for strategic context.**
- **[designs/overhaul-and-repositioning.md](designs/overhaul-and-repositioning.md)** — Full current-state assessment and the strategic repositioning brief (assistant↔companion gap). Original north-star audit document.
- **[designs/design.md](designs/design.md)** — Brand and UI design direction for "a companion that actually acts": color palette, typography, visual principles, component direction, and the build prompt for implementing the new UI.
- **[designs/react-migration-proposal.md](designs/react-migration-proposal.md)** — Tier-3 proposal (draft, awaiting sign-off) to migrate the Flask/Jinja frontend to React via Vite+React islands (strangler, chat first). Frontend inventory + toolchain options + migration path.

---

## Project context (in `.context/`, not `docs/`)

- **[../.context/project.md](../.context/project.md)** — Tech stack, directory map, architecture, how to run, known limitations.
- **[../.context/backlog.md](../.context/backlog.md)** — Prioritized work items (LAUNCH-1..5 are pre-deploy requirements; Phase 3–4 items follow).
- **[../.context/research/provider-apis-2026-07.md](../.context/research/provider-apis-2026-07.md)** — Internal research: authoritative LLM provider API shapes for Anthropic, OpenAI (Responses API), and Google Gemini (google-genai SDK); extracted from installed SDK source + official docs (July 2026). Reference before touching `src/providers/`.

---

**Maintenance:** keep this under ~60 lines; add an entry with a one-line description when you create a doc.
