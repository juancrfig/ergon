---
name: create-verification-skill
description: Use when a repo has no verification skill (.agents/skills/verify/), before Ergon builds in it. Generates the project-local skill, tool and feature map that drive the app the way a user does.
---

# Create a verification skill

Adapted from poteto's `create-verification-skill` (pstack, MIT; see `references/NOTICE.md`). His steps are kept;
what Ergon changes is in "Ergon's contract" and marked inline.

Every serious project needs a scripted way to drive the real app and prove behavior: launch it, exercise a feature
the way a user would, and capture evidence. This skill generates that as a project-local skill in
`<repo>/.agents/skills/verify/`, tailored to the repo. Ergon's Build refuses a repo without one (ADR 0033). You
write the output for the next agent, not for a human: Ergon's builder reads it cold, mid-task, having never seen
the app. The human runs you once per repo with their coding agent; they review and commit the result.

## Ergon's contract

The generated skill must fit how Ergon checks a builder's work. Hold these through every step:

- **Location and names.** `SKILL.md`, `features/README.md` (the map's index) and one file per feature in
  `features/`, plus any helper, all in `<repo>/.agents/skills/verify/`. Ergon puts `SKILL.md` and the index in
  every builder's prompt; the builder opens the feature files it needs. Keep both short for that reason.
- **Evidence is the session log.** A builder proves a criterion with the commands it ran and lines their output
  showed. Code finds each command in the builder's session log, run after its last file edit, and checks the
  recorded output holds every line. Nothing else counts. So every drive is one shell command that **returns** (a
  server starts in the background and the command exits once the app is usable); its output is plain text whose
  proving lines are **stable** (no dates, ids or timings on them); and it prints the exit code as its last line
  (`exit 1`), because one backend's log has no exit codes. A UI is proved by text the harness prints (an ARIA
  snapshot, a read element), not by a screenshot code cannot read. Screenshots may still be saved for the human.
- **The working tree stays clean.** Build sends back any changed file the task does not list, and leftover data
  skews the next proof. All instance state, scratch files and evidence live under a folder the repo's
  `.gitignore` ignores (`.verify/` at the repo root), one subfolder per run or state.
- **No installs at proof time.** The builder cannot install anything or approve a prompt. Whatever launch needs is
  installed now, by the human, and the skill says what it needs.
- **The map follows the code.** A builder that changes a feature updates its file in `features/` in the same task;
  Ergon accepts changes under `features/` with any task. Requirements stay in the wiki and the plan's stories.

## 1. Interview the repo, not the user

Answer these from the codebase and only ask the user what you cannot observe:

- **Surface:** what does a user actually touch? A web UI, a CLI/TUI, a desktop app, an API, a mobile app, a
  library? A repo can have several; pick the primary one and note the rest.
- **Run:** how does the app start locally? Prefer the repo's own documented dev command (package scripts,
  Makefile, README quickstart, the repo's AGENTS.md). Note ports, env vars, seed data, auth.
- **Drive:** how can an agent interact with it programmatically? Existing harnesses first — Playwright/Cypress
  specs, expect scripts, PTY helpers, curl-able endpoints, a debug port. Only then pick a generic recipe:
  browser/CDP for web and Electron, a tmux/PTY harness for CLI/TUI, plain HTTP for services. *Ergon:* a plain
  command-line program already is its own harness; the helper only isolates its state and prints the exit code.
- **Observe:** what evidence can be captured? *Ergon:* as text on stdout — response bodies, terminal transcripts,
  read-back DB state, exit codes, ARIA snapshots. Logs and files count when the drive prints them.
- **Isolate:** can two instances run side by side (ports, data dirs, profiles)? If not, say so in the generated
  skill: refusing to double-drive a shared instance beats corrupting the user's session.

If the checkout doesn't build or start as-is, fix that first (or report it precisely) before generating; a skill
written against a broken base teaches wrong steps. *Ergon:* a fix to product code is the human's call; ask before
making one. When an irrelevant missing asset blocks startup (a static dir the API never serves, a sample config),
the generated skill may create it, clearly marked as verification scaffolding, inside `.verify/`, and remove it in
cleanup.

*Ergon, a repo with no app yet* (the first ticket creates it): take the surface and the start command from the
brief or plan (`python3 todo.py`). Generate the skill and helper for that command, and an index that says no
features exist yet. Each builder adds the features it builds. Step 3 seeds nothing, and step 4 checks only that
the helper runs and reports the missing program clearly.

## 2. Generate the skill

Write `.agents/skills/verify/SKILL.md` with YAML frontmatter (`name: verify` and a `description` that names the
app, the surface, and when to reach for it — without frontmatter the skill never registers) and these sections,
each grounded in what the interview actually found (no placeholders left):

- **Launch:** the exact command that starts the app for verification, and how to tell it's ready (a log line, a
  prompt). Launch must reach a usable state from an empty data dir, including any migrations and seed data. Ready
  means usable, not just that a process answers. A database health check can pass while its init scripts are still
  running. Include teardown. For a short-lived CLI or TUI there is no server to keep alive: launch means build the
  binary (or install deps) once, then start each drive in its own isolated PTY or tmux session. *Ergon:* launch
  returns once ready and leaves the server in the background; the data dir is a subfolder of `.verify/`.
- **Doctor:** one read-only check that answers "is this instance worth driving?" — process up, right
  version/build, port owned by us, auth valid. An agent runs this first whenever anything looks off.
- **Drive:** the harness recipe with real selectors/commands from this repo, not examples. Prefer stable handles
  (ARIA labels, data attributes, prompt strings, route paths) over coordinates and tab order.
- **Evidence:** what to capture for a proof and where it goes. State the proof standards: exercise the real user
  path, not internal setters or test-only endpoints; capture the action and the resulting state, not just the
  final screen; verify side effects (files written, rows inserted, messages sent) alongside what's visible; mocks
  only where a production boundary already isolates the external system. When the safe path is a dry-run or test
  mode, verify what it actually skips by observing (files, network, git refs) rather than trusting its name: some
  dry-runs still touch the network or open a browser. *Ergon:* the evidence is the drive's printed output; say
  which lines prove what, and that each proof starts from a known state and reads a mutation back with a second
  command.
- **Cleanup:** how to tear down instances the run created. Never kill by process name; kill what you started.
  Cleanup removes instances and scratch state, never the evidence: proof artifacts survive the teardown, in a
  location the skill names (inside `.verify/`).
- **Helpers:** any script the skill ships is executable and its invocation is shown in the skill body. A helper
  the reader has to reverse-engineer is not a helper. *Ergon:* helpers use only what the repo already depends on;
  errors say what to do instead, and `--help` works at every level.

## 3. Seed the feature map

Create `.agents/skills/verify/features/README.md` plus one file per user-facing feature you can identify (aim for
the top 3-5 to start, from routes, commands, menus, or docs). Follow the shape in
[`references/feature-map-example/`](references/feature-map-example/), with a README index and one file per feature.
Each file answers, from the user's point of view: what the feature is, how to reach it, how to drive it with the
harness, and what observable end state proves it works. The four H2s are `Sub-features`,
`How to get to it (user POV)`, `Driving it with <harness>`, and `Gotchas`. If the seed data lacks a precondition
that a journey needs, the journey reports a failure and the reason goes in that feature's `Gotchas`. Never weaken
the journey to make it pass. The map is the repo's maintained verification source; a proof that drives one
convenient entry point is incomplete when the map lists others.

*Ergon:* the index is in every builder's prompt, so keep its preconditions and conventions to what every proof
needs, and list every feature file with one line of what it covers. A feature not yet mapped is added by the first
builder that touches it.

## 4. Prove the generated skill before handing it over

Run its own instructions end to end once: launch, doctor, drive ONE mapped feature (one is enough; the map exists
so later runs can cover the rest), capture evidence, clean up. After cleanup, confirm the evidence still exists at
the named location — a cleanup that eats the proof fails this step. Fix what fails, and run the generated cleanup
after every failed iteration too, so broken attempts don't strand processes and ports. A generated skill that was
never executed is a draft, not a deliverable. If you proved it in a stand-in for the real target (a container in
place of a fresh VM, a local stack in place of a remote one), list every setup step the stand-in did that the
target will not. Those steps stay unverified until a run on the real target covers them.

*Ergon:* run the drive exactly as a builder would, as one shell command, and check its output holds the lines
the feature file says prove it. Then confirm `git status` shows only the new skill files and the `.gitignore`
line, and no process you started is left. Show the human that output.

## 5. Offer the maintenance loop

Point the user at `maintain-verification-skill` (next to this skill) for keeping the map honest as the app
changes. Suggest a cadence only if they ask.
