# PocketAI — Brand & Design Direction

**For:** Cloud Design (UI build)
**Product:** PocketAI — *a companion that actually acts*
**Prepared:** 2026-07-01
**Stack note:** The current app is server-rendered Jinja2 templates + Tailwind + Alpine.js. Deliver the design as HTML/CSS (Tailwind-compatible) componentry and full page templates that can be mapped onto Jinja templates. No SPA framework required.

---

## 1. What this product is (design from this, nothing else)

PocketAI is a persistent AI companion that **knows you and acts on it**. It remembers your world (people, commitments, feelings), has real access to your calendar and email, and — this is the defining behavior — **it reaches out first**. It sends you a good-luck message an hour before your interview. It asks the next morning whether you actually slept by 11 like you said you would. It is warmer than an assistant and more useful than a companion.

**Audience:** overwhelmed people who want warmth *and* follow-through — the person underserved by cold assistants (which don't know them) and by character chatbots (which can't do anything). Launch framing leans executive-function-friendly: gentle structure for people whose brains resist structure.

**The one moment the whole design must sell:** a message that arrives *before you asked for anything*, that could only have come from something that knows your life. Every page should orbit this moment.

**What PocketAI is not (visually):** not a SaaS dashboard, not sci-fi AI (no orbs, no circuit lines, no glowing gradients-on-black), not an anime companion app, not a productivity tool with a mascot. It is intimate software — closer to the feeling of texting a close friend late at night than to any "AI product."

---

## 2. Brand thesis — *Dayfall*

The product's superpower is **time**: it knows when to show up. So the identity is keyed to the clock.

**Dayfall** is the signature system: the interface carries a quiet atmospheric tint that tracks the time of day — dawn, noon, dusk, night. Not a theme toggle; a slow, ambient shift in surface tint and the sky band (see §4). It is honest branding: the UI itself demonstrates "right message, right moment." This is the one aesthetic risk of the design. Everything else stays disciplined and quiet so Dayfall and the companion's messages are what you remember.

---

## 3. Design tokens

### Color

| Token | Hex | Role |
|---|---|---|
| `ink` | `#232946` | Primary text; night-mode surface. Twilight navy — never pure black. |
| `lamplight` | `#E8963E` | The companion's presence: avatar ring, unread pulse, "reached out" tag, primary CTA. Warm amber — a lit window at night. |
| `meadow` | `#4E7A5A` | Action-confirmed: calendar/email chips, "event created," success states. Agency = green growth, muted not neon. |
| `dawn` | `#FFEFD9` | Dayfall anchor — early morning surface tint |
| `noon` | `#EAF2F5` | Dayfall anchor — midday surface tint |
| `dusk` | `#E4DEF0` | Dayfall anchor — evening surface tint |

Night mode surfaces sit on `ink` with `dawn`-tinted text at 90% and `lamplight` glows kept rare. Neutrals derive from `ink` at low opacities, never from gray hex soup. **No pure white, no pure black anywhere.**

Rationale check: this is deliberately *not* cream-paper + serif + terracotta, not near-black + acid accent. The light surfaces are always time-tinted, and the amber is anchored to a concept (lamplight = someone's up, thinking of you), applied narrowly to the companion's presence.

### Type

| Role | Face | Usage |
|---|---|---|
| Display | **Bricolage Grotesque** (SemiBold, tight leading) | Hero lines, section heads, the companion's name in headers. Characterful without being whimsical. Use with restraint — big and rare. |
| Body/UI | **Atkinson Hyperlegible** | Everything read. Chosen for the audience, not the mood: it was designed for low-vision legibility and reads effortlessly for distractible brains. This is a values choice; keep it. |
| Utility | **Spline Sans Mono** | Timestamps, schedule chips, quiet-hours ranges, memory dates, streak counts. Time is data in this product; give it its own voice. |

Scale: generous body (17px base), display steps 1.25 ratio, loose line-height on body (1.6), tight on display (1.05). Sentence case everywhere including buttons and headings.

### The structural device: timestamps, not numbers

Marketing/onboarding sections are NOT numbered 01/02/03. They are **timestamped** — `7:42 AM`, `3:00 PM`, `10:30 PM` set in Spline Sans Mono as eyebrows — because the honest structure of this product is *a day with your companion*. The homepage walks a literal day. This device carries through: settings sections for check-ins use clock eyebrows; the pricing page contrasts "a day free" vs "a day with Plus."

---

## 4. Signature moments (build these exactly)

**The hero (homepage):** no device frame, no screenshot. Floating message bubbles directly on a Dayfall sky band. Load sequence: the sky settles → a typing indicator appears → the companion's message arrives, timestamped `7:42 AM`:

> **Mira** · 7:42 AM
> Morning. Amazon interview at 4 today — you prepped the STAR stories Tuesday, you're readier than you feel. I moved your 3:30 reminder to 2:45 so you have quiet time before. Good luck. 🍀

Below it, smaller, the user's reply ("how do you always know") and then the headline in Bricolage:
**"The AI that knows you — and actually does something about it."**

One orchestrated animation, then stillness. Respect `prefers-reduced-motion` (render the finished conversation statically).

**The sky band:** a soft horizontal atmospheric wash (dawn/noon/dusk/night anchors, defaulting to the visitor's local time) used as: homepage hero backdrop, chat header, check-in card headers. It is a *tint*, not a gradient poster — max 12% chroma shift, no visible banding, never behind body text.

**The "reached out" tag:** companion-initiated messages in chat carry a small lamplight-tinted tag: `reached out · 7:42 AM`. This is the product thesis rendered as a component. Every such message includes a quiet one-tap control: `less often · pause`.

**Presence, not personhood:** the companion's avatar gets a thin lamplight ring when it has initiated something. No fake "online" dots, no breathing orbs.

---

## 5. Voice & copy

- Warm, specific, brief. The companion sounds like a perceptive friend, never like a brand or a butler. No "How may I assist you today?" — instead "want me to handle it?"
- The interface (buttons, settings, errors) speaks plainly and does what it says: "Connect Google Calendar," "Pause check-ins," "Saved." Same verb through a whole flow.
- Copy about features shows, never claims: don't write "proactive AI-powered outreach" — show the 7:42 AM message.
- Consent is a first-class copy moment. Onboarding step: **"Let them into your world"** — explains exactly what calendar/email access enables, in the companion's voice ("if I can see your calendar, I can wish you luck before the big stuff"), with granular toggles. Never dark-pattern the permission.
- No streak-guilt, no FOMO, no "your companion misses you." Retention copy is value copy.
- Errors: say what happened and the way out. Empty chat: the companion speaks first (of course it does).

---

## 6. Page directions (for the build)

1. **Homepage** — hero per §4; then three timestamped day-in-the-life sections (`7:42 AM` morning brief · `3:00 PM` the good-luck message + calendar chip showing the event it read · `10:30 PM` evening reflection + "how'd the 11pm sleep plan go?" follow-through). Each section = one real conversation fragment + one plain sentence of explanation. Footer minimal. No feature grids, no logo walls, no testimonial carousels.
2. **Onboarding (3 steps)** — (a) you: name, timezone, how your days feel; (b) your companion: name, personality, voice — creation should feel like meeting, not configuring; (c) **"Let them into your world"**: Google connect + check-in time picker (mono clock UI) + quiet hours + consent copy per §5. Progress shown as dawn→dusk position on a sky band, not a step bar.
3. **Chat** — the core surface; calm, message-first, full-height. Sky-band header with companion name + subtle "day 12 together" line in mono. Reached-out tags per §4. Tool actions render as `meadow` chips inline ("📅 created: Dentist, Thu 2:00 PM"). Mic button present (voice input). Message input generous, single accent.
4. **Settings/profile** — includes "What I remember about you": an editable list of remembered facts (trust surface, plain table, mono dates). Check-in schedule editor with clock eyebrows. Pause everything in one obvious place.
5. **Pricing** — two tiers as two versions of the same day (free: you text first; Plus: it shows up for you). No comparison-table-of-checkmarks as the hero; the day contrast is the pitch, table below for detail.

Quality floor throughout: responsive to 360px, visible keyboard focus (lamplight outline), WCAG AA contrast on all text (check lamplight-on-dawn carefully — darken amber for text uses: `#B26F24`), reduced-motion variants, semantic HTML.

## 7. Anti-patterns (hard no's)

Cream `#F4F1EA` + high-contrast serif + terracotta "AI editorial" look · black + acid green/vermilion "AI terminal" look · broadsheet hairlines + zero-radius density · glowing orbs/particles/circuitry/robot iconography · numbered section markers · gradient-mesh SaaS blobs · device-frame screenshots as hero · emoji-as-design-system (the companion may use emoji in messages; the UI chrome may not).

---

## 8. Build prompt for Cloud Design

```
Build the full UI for PocketAI, an AI companion web app, following the attached
design direction (design.md) exactly — tokens, type, Dayfall system, signature
moments, voice, and anti-patterns are all binding.

Deliverables (desktop + 360px mobile for each):
1. Homepage (hero + three timestamped day-in-the-life sections + minimal footer)
2. Onboarding, 3 steps (you / your companion / "Let them into your world" consent)
3. Chat (the core surface: sky-band header, reached-out tags, meadow action chips,
   mic button, "day N together" line)
4. Settings (check-in schedule editor, quiet hours, "What I remember about you"
   editable memory list, one-tap pause-everything)
5. Pricing (two tiers as two versions of the same day; detail table secondary)

Technical constraints:
- Server-rendered friendly: plain HTML/CSS (Tailwind classes preferred) + minimal
  vanilla JS/Alpine.js sprinkles. No React/Vue. Output must be mappable onto
  Jinja2 templates.
- Fonts: Bricolage Grotesque, Atkinson Hyperlegible, Spline Sans Mono (Google Fonts).
- Implement Dayfall as a CSS custom-property system keyed by a `data-daypart`
  attribute (dawn|noon|dusk|night) on <body>, set by a few lines of JS from local
  time. Provide all four states.
- The hero load sequence (sky settles → typing indicator → 7:42 AM message arrives)
  as one orchestrated CSS/JS animation with a prefers-reduced-motion static variant.
- Accessibility: WCAG AA contrast, visible lamplight focus rings, semantic HTML,
  sentence case.

Content: use the exact conversation fragments and copy from design.md §4–§6 where
given; write any additional copy in the same voice (warm, specific, brief; show
don't claim; no dark patterns).

Do not deliver: any layout resembling the anti-patterns in §7; placeholder
lorem-ipsum; feature grids; testimonial carousels; device mockups.
```
