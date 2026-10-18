---
name: smooth-frontend
description: Use when designing a task for a frontend agent, or building a visual interface for humans. Holds the human's taste and the component library to build from.
---

# Smooth frontend

The human's personal taste for visual interfaces, and the library of components agents build from. The human
approves every change to this skill.

## Taste: motion

Adopted from Emil Kowalski ("You don't need animations", and his design-engineering skill). Canonical copy:
`juancrfig/memory` `frontend/rules/004-motion.md`.

**Decide.** Before animating, name how often a user sees it and its purpose. No answer, no animation.

- Hundreds of times a day (keyboard shortcuts, command menu, key navigation): no animation, ever. No action started
  from the keyboard animates.
- Tens of times a day (hover, list navigation, tab switches on work screens): instant, or barely there.
- Occasional (dialogs, drawers, toasts, dropdowns): standard animation.
- Rare or first-time (onboarding, feedback forms, celebrations): delight is allowed.
- Valid purposes: spatial consistency (enter and leave from the same side), a change of state, explaining a feature,
  press feedback, preventing a jarring appear or disappear. "It looks cool" is not a purpose for anything seen often.
- Match motion to the mood: daily work tools are crisp and fast.

**Hover.** A color shift, never motion. Daily work screens: the color changes instantly. Screens seen rarely
(landing, login, showcase): a fade of at most 150ms, `ease`. Hover only behind `@media (hover: hover) and
(pointer: fine)`.

**Speed.** Interface animations stay under 300ms. Press 100–160ms; tooltips and small popovers 125–200ms; dropdowns
150–250ms; dialogs, drawers and view changes 200–300ms (up to 500ms only on screens seen rarely); marketing may be
longer. Exit is faster than enter: slow where the user decides (hold-to-delete 2s linear), fast where the system
answers (release 200ms). The first tooltip waits; the next ones open instantly with no animation. A faster spinner
makes loading feel faster.

**Easing.** Enter or leave: ease-out. Move on screen: ease-in-out. Color: ease. Constant motion: linear. Never ease-in.
Use strong curves: `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`, `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`,
`--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1)`. Springs for drag, interruptible gestures and objects that should feel
alive; bounce 0.1–0.3, only for drag-to-dismiss or playful pieces.

**Craft.**

- Pressables scale to 0.97 on press (range 0.95–0.98).
- Nothing enters from `scale(0)`: start at `scale(0.95)` with opacity 0.
- Popovers grow from their trigger (Base UI: `transform-origin: var(--transform-origin)`). Dialogs stay centered.
- Transitions, not keyframes, for anything triggered rapidly: transitions change course, keyframes restart.
- Name animated properties; never `transition: all`. Animate only `transform` and `opacity` (`clip-path`, `filter`
  when needed), never width, height, padding or margin.
- In Motion (Framer Motion) under load, animate the full `transform` string, not the `x`/`y`/`scale` shortcuts. Prefer
  CSS for animations decided in advance.
- A crossfade that looks like two objects swapping gets a light blur during it (about 2px, under 20px).
- Stagger groups 30–80ms per item; never block input while it plays.
- Drag: dismiss on a quick flick (speed), not only distance; friction at the edges instead of hard stops; capture the
  pointer; ignore extra fingers once a drag starts.

**Accessibility.** Reduced motion means fewer and gentler animations, not zero: keep opacity and color, remove
movement.

**Review.** Watch new animations in slow motion or frame by frame, look again the next day, test gestures on a real
phone.

## Taste: layout and flow

Learned from walking a point-of-sale app as a first-time cashier.

**Navigation by role.** Group screens by who uses them, not by data area. List the roles first (for example cashier,
waiter, kitchen, owner) and the jobs each one does in a shift. Each role sees only its own tabs, at most four or five.
A single-purpose role (kitchen, bar) gets one full screen with no navigation. A device remembers its role. Screens a
role never needs are not in its menu, even as icons.

**Walk it as the user.** Before building, take each role's real jobs ("sell 3 burgers and 2 mojitos", "receive a meat
delivery", "close the day") and ask, starting from the first screen: is it obvious where I go? Assume the user knows
the business but none of the code or the design conversation. Any guess or tap-around is a finding. After building,
run the walkthrough protocol below.

**Interfaces sit on the CLI.** Every job a screen does must also work through the CLI, so an agent can do it from a
voice note or chat. The web is one optional shell; design the CLI command first, then the screen over the same
domain function.

**Show inputs as they become needed (progressive disclosure).** Start with only the inputs that are mandatory or that
decide which inputs come next. Reveal the next inputs when an earlier answer makes them relevant. Optional extras
(notes, free lines, due dates, invoices) hide behind one small "+" action. Do not take it to the extreme: a short form
whose fields are always needed stays one form.

**Collapse what is answered.** Once a value is entered, shrink it to a compact summary or chip ("2 × Hamburguesa ·
$50.000", "Efectivo") that stays editable with one tap. The screen grows with the work, not with the possibilities.

**No fixed counts.** Never hard-code "item 1, item 2 (optional)" slots. Any list the user builds (sale lines, order
lines, recipe ingredients, purchase lines) is a repeatable row with "+ añadir"; the domain limit is the only limit.

**Pick from growing lists by search and tap, not a long select.** Catalogs that grow (recipes, items) use a search
field plus large tap targets grouped by type (comida / trago), most used first. A tap adds one; +/− adjusts quantity.

**Show the result before the commit.** A form that records money shows the running total and its parts before the
submit button.

**Action screens and status screens are separate.** A screen for doing a job (record a sale) does not also carry
dashboards (balances, summaries, logs). Status lives in its own place, for the role that reads it.

**Code follows the sections.** One module or folder per section (per role area), plus one shared layer for layout,
navigation and common pickers. A section never imports another section, and no file grows past what an agent reads
comfortably (about 400–600 lines). An agent fixing one section then loads only that section. A single 2,300-line
web file was the incident.

**Icons.** Icon-only buttons only where the meaning is universal (+, ×, delete, refresh, back). Navigation tabs keep a
short text label under the icon: in a walkthrough, most icon-only tabs were ambiguous to a first-time user.

## Walkthrough protocol (last verification layer)

The human approved this as the final check of every human interface, after the gate, the review and the merge
dry run. It finds what code review misses: missing flows, dead ends, fixed limits, and data that one role
creates but another role never receives (for example a counter sale that sent nothing to the kitchen).

1. **Scenarios first.** Write the 80/20 jobs for each role from the real business, not from the screens: the jobs
   done every shift, the rush-hour version, the mistake and its correction, and the hand-off to another role.
   Get them from the spec and the human's words; mark the ones you assumed.
2. **Safe copy.** Run the app from a clean copy with a throwaway database and realistic seed data (a full menu, stock,
   open tables, an open day). Never production.
3. **Walk as the user.** Phone width first (390×844), then desktop. For each scenario start on the role's first
   screen and do the job only with what the screen shows. Record every point where you had to guess, scroll to find,
   type something the system already knows, or could not finish.
4. **Follow the hand-off.** After each job, open the screen of the role that must react (kitchen, cashier, owner)
   and check the result arrived there.
5. **Same job by CLI.** Do each scenario once through the CLI, as the voice/chat agent would. A job the web can do but
   the CLI cannot is a finding.
6. **Report** findings ranked by frequency × pain: what the user tried, what happened, what they needed. Separate
   screen-only fixes from domain changes; domain changes go to the human before any task.

## Component library

Free resources only. Two layers:

- **Base components**: the everyday interface pieces (buttons, forms, tables, dialogs, tabs). Every screen is built
  from these.
- **Accents**: visual identity for a few showcase places (hero, background, login, loading). The screen must look
  complete without them.

### Base components

- **[shadcn/ui](https://ui.shadcn.com), style `base-nova`** (MIT): copy-in components built on
  [Base UI](https://base-ui.com) (MIT), with shadcn's compact Nova style and the Geist font. Use it as delivered.
  Set up a project with `npx shadcn init` and choose Base UI and Nova (`"style": "base-nova"` in
  `components.json`). Add components with `npx shadcn add <component>`.
- When the human wants a component personalized beyond Nova, build it directly on a bare Base UI component.
  Do this only when the human asks.

Still being curated with the human: data tables, date pickers, charts, toasts, empty and loading states.

Other base sources, used only where shadcn has no matching component:

- **[coss ui](https://coss.com/ui)** ([GitHub](https://github.com/cosscom/coss)): Cal.com's design system. 50+
  copy-in components and 500+ pre-assembled "particles", also on Base UI and Tailwind, plus a skill and `llms.txt`.
  **On hold: AGPL-3.0.** A web app that copies AGPL code may have to publish its own source to its users. Do not
  use it until the human decides.

### Motion components

Animated versions of everyday pieces. Use them only where an animation has a purpose (see the human's taste).

- **[beUI](https://beui.dev/components/motion)** ([GitHub](https://github.com/starc007/ui-components), MIT; a paid
  Pro tier exists, use the free part only): 50+ components, 20+ blocks and 18 AI-agent components, built with
  Motion and Tailwind. Copy the TypeScript source. Many support reduced motion; keep that when adapting one.
- **[Transitions.dev](https://transitions.dev)** ([GitHub](https://github.com/Jakubantalik/transitions.dev)): 43+
  CSS/React transitions and a free agent skill. Free for commercial use; we may not redistribute the library itself.
  Pro (paid) recipes are out. Its Motion Agent (`npx transitions-agent`) scores a codebase's motion from 0 to 100,
  locally and without AI: a candidate deterministic check for the verification guide, not yet tried.
- **[Rare UI](https://www.rareui.com/components)** ([GitHub](https://github.com/swamimalode07/rare-ui)): 24+
  unusual components (gooey nav, proximity sidebar, duration picker), installed with the shadcn CLI. License is MIT +
  Commons Clause + attribution: **every app that ships one must show a visible link to rareui.com** (footer, about
  page or README), and must not resell the components.

### AI-agent interfaces

For screens where a person works with an agent: thinking traces, tool calls, approval cards, streamed answers.

- **[Beautiful UI](https://www.beautifului.dev)** (MIT): 21 pieces: loading state, thinking, streaming text with
  sources, approval card, tool chips, task rows, chat, prompt bar, recommendation card, context cards, diff table,
  records table, filter table, flowchart and others.
- beUI's AI-agent section (above) covers the same ground.

### Accents

- **[Shaders](https://github.com/shader-effects-inc/shaders)** (MIT; the shaders.com editor is free with an account,
  its presets and sections are paid): 200+ WebGPU effects as components for React, Vue, Svelte, Solid and JavaScript.
  Use only on showcase screens, never on daily work screens. Browsers without WebGPU show nothing, so the
  screen must work without the effect. For an agent: `npx shaders skill` and https://shaders.com/llms-full.txt.
- **[Radiant](https://radiant-shaders.com)** ([GitHub](https://github.com/pbakaus/radiant), MIT, no paid tier): 50+
  shaders and effects (flow fields, silk, aurora-like glows, black holes), each one self-contained HTML file with no
  dependencies and no build step. Use: copy the file's source and adapt it (colors from the theme tokens, timing).
  Most use WebGL or Canvas 2D, which more browsers support than WebGPU. Most respect `prefers-reduced-motion`
  (the user's setting to reduce animation); keep that when adapting one. Same limits as above: showcase screens
  only, and the screen must work without the effect.

## Sources for later

Not used by any agent yet. Kept for the frontend role redesign (theSystem issue #41).

- **[UI Skills](https://www.ui-skills.com)** ([GitHub](https://github.com/ibelick/ui-skills), MIT): a catalog of
  design skills with a CLI and an MCP server. Candidates: `improve-ui` (audits a screen and writes plans for another
  agent), `better-ui` (polish details), `web-design-guidelines` (accessibility and UX review), Emil Kowalski's
  `improve-animations`, and Anthropic's `frontend-design`. Emil's own collection is at
  [emilkowalski/skill](https://github.com/emilkowalski/skill) (MIT): `review-animations`, `animation-performance`,
  `pick-ui-library` and others.
- **[Design System Checklist](https://www.designsystemchecklist.com)**
  ([GitHub](https://github.com/ardakaracizmeli/design-system-checklist), no license file): 230 checks in four
  groups: design language (10), foundations (26), core components (166), maintenance (28). Candidate protocol for
  designing a design system per company or project. Use it as a checklist to follow, not as text to copy.
