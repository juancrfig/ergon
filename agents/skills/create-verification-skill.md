---
name: create-verification-skill
description: Use when a repo has no verification skill (.agents/skills/verify/), before Ergon builds in it, or when its feature map drifted. Builds the app's agent tool, SKILL.md and FEATURES.md with the human.
---

# Create a verification skill

Ergon's builder proves every criterion by driving the real app (ADR 0033), and Build refuses a repo without
`.agents/skills/verify/SKILL.md` and `FEATURES.md`. You write them, once per repo, with the human: you run in their
coding agent, so ask them whatever the code cannot answer. They review and commit the result; you commit nothing.

What you make, all in `<repo>/.agents/skills/verify/`:
- **The tool**: a small command-line program that starts, drives, inspects and stops the app. It is the *lever*:
  one command instead of a throwaway script per check, so every builder drives the app the same way.
- **SKILL.md**: how to use the tool and what counts as proof. Ergon puts it in every builder's prompt.
- **FEATURES.md**: the feature map, what the app does and how a user reaches each feature. Navigation only;
  requirements live in the wiki and the plan's stories. Ergon puts it in every builder's prompt too.

## How the builder's proof is checked
Design every part for this check. The builder answers with, per criterion, the commands it ran and lines their
output showed. Code finds each command in the builder's session log, run after its last file edit, and checks the
recorded output holds every line. So:
- Every check is one shell command that **returns**: a server starts in the background, and the command exits once
  the app is ready.
- Output is plain text with **stable lines**: the result a criterion is about, on its own line, without dates, ids
  or timings mixed in. Print the app's exit code as a last line (`exit 1`), because one backend's log has no exit
  codes.
- **State stays out of the working tree.** Build sends back any changed file the task did not list, and data left by
  one check skews the next. Keep all app state under a folder the repo's `.gitignore` ignores, named per run, so a
  check starts from a known state.
- The builder cannot install anything or approve a prompt. Everything the tool needs is installed now, by the human.

## Steps
1. **Learn the app.** Read the repo's AGENTS.md and README, its entry points and how it runs today. Done: you can
   name every surface a user touches (commands, routes, screens) and the one command that starts the app.
2. **Ask the human, in one batch,** what the code does not say: seed or test data, test users and logins, external
   services (a staging environment or a fake behind the same boundary), ports, and anything a check must never
   touch. Done: every precondition has an answer, or is named manual.
3. **Build the tool.** Start from the smallest one the app allows; a command-line app needs only a wrapper that
   runs it in a named state folder and prints the exit code. A server or UI app needs more:
   - `start` (waits until ready), `stop` (ends the whole process group), `status` (running, port, stale build);
   - `reset <state>` to a known state, from the seed the human named;
   - one subcommand per way of driving or inspecting the app (send a request, read a record, click a labelled
     control, read a screen's text), composable, so a proof is a few calls;
   - errors that say what to do instead, `--help` at every level, `--dry-run` on anything destructive, and output
     a model reads easily (stable text lines; JSON when the result is structured).
   Use only what the repo already depends on. Add the state folder to `.gitignore`. Done: from a clean checkout,
   start, one drive command and stop work, and stop leaves no process behind.
4. **Write FEATURES.md.** Walk the app as a user and record every feature. Per feature, four headings: what it does,
   how a user reaches it, how to drive it with the tool (example commands), and gotchas (what usually lies, what is
   manual). Keep entries behavior-level and short enough to drive without reading the source. Done: every surface
   from step 1 has an entry.
5. **Write SKILL.md.** Frontmatter `name: verify` and a description naming the app. Then: how to start, check
   status and stop; the command surface (`--help` holds the detail); the proof bar; how to clean up. The proof bar:
   drive the user's path, not internal functions; for each criterion cover the paths the change touches (success,
   error, empty, persistence); prove persistence by reading the state back through a second command; start each
   proof from a reset state. Keep it to what every proof needs. Done: a builder with only SKILL.md and FEATURES.md
   can prove a criterion on any feature.
6. **Prove the skill.** Act as a builder: pick two features, and for each run a proof from a reset state exactly as
   SKILL.md says, then stop everything. Done: both proofs printed the lines you expected, `git status` shows only the
   new skill files and the `.gitignore` line, and no process is left. Show the human that output.
7. **Hand over.** List what you made and what stays manual. The human reviews and commits.

## A repo with no app yet
When the repo is empty because the first ticket creates the app, write the skill for the entry point the plan or
brief names (`python3 todo.py`): the tool, SKILL.md, and a FEATURES.md that says no features exist yet. Each
builder adds the features it builds. Skip step 6's proofs; check only that the tool runs and reports the missing
program clearly.

## Maintain
When run on a repo that already has a verification skill, compare FEATURES.md and the tool against the app: add
missing features, fix wrong paths, remove features that are gone, and repair commands that fail. Builders keep the
map current as they work; this pass catches what they missed. Report what changed; the human commits.
