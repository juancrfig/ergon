# Wizard: create a project's verification guide

Output: `<project>/agents/skills/verify-<project>/` with `SKILL.md` and `features/`. Write it for an agent that
reads it cold, mid-task, and has never seen the app. Follow `writing-docs`.

## 1. Interview the repository, not the human

Answer each question from the code, README, scripts, configs and legacy flows. Done when every question has an
answer with a file citation, or is on the list for the human.

- **Surface**: what does a user touch? Web UI, API, CLI, scheduled job, mobile app. Note all; name the primary one.
- **Launch**: the repository's own command to start the app locally; ports, environment variables, seed data, auth;
  the signal that it is ready.
- **Hands**: how an agent can drive it. Web and mobile apps: e2e (see the main skill), set up with `npx e2e init`;
  keep the `e2e mcp` live mode and create no test files. Services: HTTP. Jobs: a direct command.
- **Views**: where each of the four views is read: logs, rendered output, boundary traffic, stored state.
- **Isolation**: can a run start its own instance (own port, own data directory or database)? If not, say so.
- **Legacy**: does the app replace an existing flow (n8n, scripts, sheets)? That flow holds tolerances the new code
  must keep.

## 2. List the real data sources

One line per external source the app reads or writes (spreadsheet, database, chat, API). For each: what it is, how
an agent reads it, and the access the human grants:

- `none`: agents use a local copy only.
- `read-only`: agents read the real source.
- `sandbox-write`: agents write only to a named sandbox (test database, sheet copy, test chat).

Ask the human for every access level in one message. Never assume one. Done when every source has a level from
the human.

## 3. Write `SKILL.md`

Front matter `name: verify-<project>` and a description that names the app and when to use it. Sections, each filled
with real commands from this repository (no placeholders):

- **Launch**: start command, ready signal, teardown.
- **Doctor**: one read-only check that the instance is the right app, build and data, before any drive. Run it
  first, and again after anything surprising.
- **Drive**: how the hands work, with stable handles (labels, roles, routes, command names), never coordinates.
- **Observe**: where to read each of the four views.
- **Data sources**: the list from step 2, with access levels.
- **Evidence**: what to capture as proof and where it is kept.
- **Cleanup**: stop only what this run started; keep the evidence.

## 4. Seed the feature map

`features/README.md` (index, shared preconditions) plus one file per user-facing feature: the top 3 to 5 to start.
Use [../templates/feature.md](../templates/feature.md). Gotchas come from reading the real sources and the legacy
flow: header variants, empty values, time zones, duplicates. Done when every seeded feature has an observable end
state that proves it works.

## 5. Prove the guide once

Run it end to end: launch, doctor, drive one mapped feature, capture evidence, clean up. Confirm the evidence still
exists after cleanup. Fix what fails and run cleanup after every failed attempt. Done when one feature was proved;
until then the guide is a draft.

## 6. Hand over

Report to the human: the guide's location, the feature proved and its evidence, data source access levels, helper
scripts that need approval, and what could not be driven and why.
