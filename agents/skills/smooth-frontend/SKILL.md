---
name: smooth-frontend
description: Use when designing a task for a frontend agent, or building a visual interface for humans. Holds the human's taste and the component library to build from.
---

# Smooth frontend

The human's personal taste for visual interfaces, and the library of components agents build from. The human
approves every change to this skill.

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
