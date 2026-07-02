# PocketAI — Design Brief for Claude Design

**Product:** PocketAI — *a companion that actually acts*
**Prepared:** 2026-07-02 (v2 — supersedes the v1 doc that prescribed a palette/type system and a time-of-day "Dayfall" theme; both are retired. Visual language is now fully Claude Design's call.)
**Stack note:** Server-rendered Jinja2 + Tailwind + Alpine.js. Deliver HTML/CSS (Tailwind-friendly) page templates + components mappable onto Jinja. No SPA framework.

---

## 1. What PocketAI is

A persistent AI companion that **knows you and acts on it**. It remembers your world (people, commitments, feelings), has real access to your calendar and email, and — the defining behavior — **it reaches out first**. It sends a good-luck message an hour before your interview. It asks the next morning whether you actually slept by 11 like you said you would.

It sits in the gap between two categories:
- **Task assistants** (ChatGPT, Claude): can do things, but don't know you and never think of you.
- **AI companions** (Character.ai, Replika): know you, but can't do anything about it.

PocketAI is warmer than an assistant and more useful than a companion. The retention model is **relationship + follow-through**, never engagement mechanics.

**The one moment every page must sell:** a message that arrives *before you asked for anything*, that could only have come from something that knows your life. Example (real product behavior, use freely as content):

> **Mira** · 7:42 AM
> Morning. Amazon interview at 4 today — you prepped the STAR stories Tuesday, you're readier than you feel. I moved your 3:30 reminder to 2:45 so you have quiet time before. Good luck.

Show this moment; don't describe features.

## 2. Target audience

**The overwhelmed-but-wants-warmth person.** Launch framing leans executive-function-friendly: people whose brains resist structure but who respond to a warm presence that gently keeps their life on track — follow-through, timely nudges, remembering what they said mattered. They are underserved by cold productivity tools and by character chatbots that can't touch a calendar.

They are ordinary consumers, not AI enthusiasts. The product should feel like intimate software — closer to texting a close friend than to operating a SaaS tool.

## 3. Brand identity (personality, not pixels)

- **A perceptive friend, not a butler and not a therapist.** Warm, direct, a little playful. Never clinical, never corporate, never "wellness." If a screen would look at home in a meditation app, it's wrong.
- **Competent intimacy.** The magic is the *combination*: it cares AND it did something. Design moments should pair warmth with evidence of action (the message plus the calendar change it made).
- **Trustworthy about its access.** It reads your calendar and email — the design must make that feel chosen and controlled, never surveilled. Consent, memory, and "pause everything" are first-class surfaces, not settings-page afterthoughts.
- **The companion is the star; the app is the frame.** Users name and shape their companion — the interface should recede and let the conversation carry personality.

## 4. Design philosophy

- **Show, don't claim.** Real conversation fragments and real actions taken beat any feature copy. The homepage's job is to make a visitor *feel* being known.
- **Calm confidence over spectacle.** No AI-product tropes: no orbs, glows, particles, circuitry, robot iconography, gradient-mesh blobs. This must not look like every 2026 AI landing page — and equally not like a template. Make opinionated choices; we hired a designer, not a theme.
- **Text is the product.** Messages are the primary content everywhere; typography and rhythm of conversation deserve the design attention a photo app would give images.
- **No dark patterns, ever.** No streak-guilt, no "your companion misses you," no manufactured FOMO. Every proactive message carries a one-tap "less often / pause." Retention comes from being genuinely useful.
- **Copy voice:** plain, specific, sentence case. Buttons say what they do. The companion sounds like a person; the interface stays out of character and stays quiet.
- **Quality floor:** responsive to 360px, WCAG AA contrast, visible keyboard focus, `prefers-reduced-motion` respected, semantic HTML.

**Explicitly delegated to Claude Design:** palette, typography, iconography, motion language, layout systems, structural devices. Bring a distinctive point of view; the only constraints are the personality above and the anti-tropes list.

## 5. Pages & functional requirements (visuals unspecified)

1. **Homepage** — hero built around the companion-texts-first moment; a short day-in-the-life narrative works well as structure (morning nudge → pre-event encouragement → evening follow-through). Minimal footer. No feature grids, logo walls, or testimonial carousels.
2. **Onboarding (3 steps)** — (a) about you (name, timezone, how your days feel); (b) create your companion (name, personality, voice) — should feel like *meeting someone*, not configuring software; (c) **"let them into your world"**: Google connect, proactive-messages consent, daily check-in time, quiet hours — framed in the companion's voice ("if I can see your calendar, I can wish you luck before the big stuff"), honest about access, granular toggles.
3. **Chat (the core surface)** — message-first, full-height. Must accommodate: companion-initiated messages with a subtle "reached out" indicator + inline "less often / pause" affordance; inline chips when the companion acted (event created, email sent — with the draft→confirm flow: the companion shows a draft, the user confirms in chat); a mic button (records, transcript lands in the input for review before sending); voice-message playback on companion replies; a quiet relationship line (e.g. "day 12 together") — informational, never gamified.
4. **Settings** — check-in schedule + quiet hours editor; **"what I remember about you"**: an editable, deletable list of remembered facts (trust surface); one obvious "pause everything."
5. **Pricing** — free vs Plus told as two versions of the same day (free: you text first; Plus: it shows up for you). Comparison table secondary. (Note: one legacy pricing bullet is under separate legal review — omit "uncensored models" from any new copy.)

## 6. Build prompt for Claude Design

```
Design and build the full UI for PocketAI, an AI-companion web app, from the
attached brief (design.md). Sections 1–4 define the product, audience, brand
personality, and design philosophy — these are binding. Section 5 lists the
pages and their functional requirements.

You own the complete visual language: palette, typography, motion, layout,
iconography. Bring a distinctive, opinionated direction that fits "a
perceptive friend who actually acts" — warm, competent, intimate software.
Hard exclusions: meditation/wellness-app aesthetics; AI-product tropes (orbs,
glows, particles, circuit motifs, gradient-mesh blobs); dark patterns;
generic template looks.

Deliverables (desktop + 360px mobile each): homepage, 3-step onboarding,
chat, settings, pricing — per §5's functional requirements, including the
companion-initiated message treatment, action chips with draft→confirm,
mic/voice affordances, editable memory list, and consent-forward onboarding.

Technical constraints: server-rendered friendly — plain HTML/CSS (Tailwind
preferred) + vanilla JS/Alpine.js sprinkles, no SPA framework; output
mappable onto Jinja2 templates. Accessibility floor per §4. Use the §1
conversation fragment as hero content; write any additional copy in the
brief's voice (plain, specific, show-don't-claim).
```
