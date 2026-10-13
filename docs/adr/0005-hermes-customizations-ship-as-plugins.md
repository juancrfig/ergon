# ADR 0005: Hermes customizations ship as theSystem plugins, not Hermes fork commits

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

theSystem needs to change some Hermes behavior, for example enforcing labeled memory writes (F11). `hermes update`
keeps the install on the official upstream: it saves local commits on `main` to a rescue ref and resets the branch.
A change committed into the Hermes checkout therefore disappears on the next Hermes update, without warning.

## Decision

- Change Hermes behavior only through Hermes's plugin interface (for example a `pre_tool_call` hook), with the plugin
  kept in this repository and installed by theSystem's installer.
- Never commit to, or patch, the Hermes checkout.

## Consequences

- Customizations survive Hermes updates, and every instance gets them through `update`.
- A behavior that the plugin interface cannot reach needs an upstream Hermes change or a new hook, not a local patch.
- A Hermes update can change the plugin interface; the Monitor's plugin checks run after each Hermes update to catch it.
