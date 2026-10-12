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
