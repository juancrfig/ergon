---
name: verification-heuristics
description: Use when designing, creating or judging how agents verify their work, or when a project has no verification guide or gate. Holds the three classes, the gate contract, proof standards and the wizard that creates a project's guide.
---

# Verification heuristics

The philosophy every verification system in this workspace follows, plus the wizard that turns it into one
project's verification guide. The general tenets are in [theSystem tenets](TENETS.md); each project's
guide makes them concrete.
The human approves every change to this skill.

## Tenets

See [theSystem tenets](TENETS.md).

## Three classes of verification

- **Gates**: compile, type check, build. Fast, offline, no model, the same verdict every time. No approval: workers
  run them, and the orchestrator runs them again.
- **Evidence runs**: launch the app and drive it like a user (the verification loop below). Need the human's
  explicit ask.
- **Tests**: automated tests, written at the end of development. The human approves each test.

Gates come first because they are the 80/20: the cheapest checks catch most errors. Why: incident 1 (a missing
quote) passed a worker re-read and two reviewers; a build catches it in seconds.

## Gates

Each project has one gate, declared in its guide as `verify-<project>/gate.json` and run with
[scripts/gate.py](scripts/gate.py). The contract and the standard recipes per stack are in
[references/gate.md](references/gate.md). In short:

- One interface for every project; the stack's tools stay inside the gate's steps.
- Red or green by exit code, never by a model's judgement.
- The agent gets the tools' own messages in full, from every step, with a summary on top. Never only "error".
- Fast (about 2 minutes), offline after setup, no real data, no secrets. Anything else is not a gate.
- Every new project gets its gate before its first feature task. A project without a gate stops the run.

## The verification loop

An agent verifies the way a developer uses browser DevTools: it **acts** on the app, then **observes** four views.

- **Hands**: drive the real app the way a user does (open the page, fill the form, run the job once).
- **What broke**: logs and error output of every process involved (browser console, server, scheduled job).
- **What the user sees**: the rendered result, read as text (accessibility tree, CLI output, response body).
- **What crossed a boundary**: every request and response to an external system (HTTP, SQL, Google Sheets, Telegram).
- **What was saved**: the stored state after the action (database rows, files, browser storage).

A change is verified when the hands exercised it and the views show the expected result.

### Hands for web and mobile: e2e

[e2e](https://e2e.tester.army/docs) ([GitHub](https://github.com/tester-army/e2e), Apache 2.0) is the canonical
tool for end-to-end work in this workspace. Adopted untried; the first project guide is its trial.

- **Evidence runs** use its live mode, `e2e mcp`: each agent opens its own session of the app and drives it. It
  writes no test files. Read the step verdicts as they are: `passed`, `failed`, or `blocked` (the environment or a
  precondition stopped the step; report it as unreachable, never as verified).
- **End-to-end tests** are written with e2e, and only when `rules/tests-and-verification-need-human-approval.md`
  allows them.
- Every agent step costs model calls; replays of verified steps do not.

## Project verification guide

Each project has one guide: the project-local skill `verify-<project>` in `<project>/agents/skills/`. It says how to
launch, check, drive, observe and clean up the app, which real data sources agents may touch, and a feature map.
Its first entry is the gate (`gate.json`); a guide may hold only the gate until the wizard runs.

- No guide: create it with the wizard in [references/create-guide.md](references/create-guide.md).
- A guide never proved end to end is a draft. A run that needs it stops and reports instead of guessing.
- **Wiki or feature map**: a fact an agent can check by driving the app or reading a data source belongs in the
  feature map. A fact that explains why (business, decisions, regulation) belongs in the wiki. Each fact has one
  owner; the other place links to it.

## Proof standards

- Exercise the real user path. Internal setters, test-only endpoints and injected state are not proof.
- Capture the action and the resulting state, not only the final screen.
- Check side effects (rows written, files created, messages sent) as well as what is visible.
- Read real data sources through the access the guide grants. A local copy or a description is not the source.
- Observe what a dry run or test mode skips; do not trust its name.
- Report a path that could not be reached, with the command tried and the missing precondition. Never report it as
  verified through another path.
- Keep the proof after cleanup, where the guide says.

## Boundaries

- Gates need no approval. Evidence runs and tests follow `rules/tests-and-verification-need-human-approval.md`.
- Evidence runs leave proof, not code.
- A gate's steps, and helper scripts a guide ships, are changes the human approves like any change to the project.
- Agents touch a real data source only with the access the guide records for it. The human sets that access.
- Asking for the wizard, or for an evidence run, is the human's explicit ask for it.

## How this skill grows

Every verification failure comes with a proposal that prevents it from happening again. Place the fix at the
strongest layer that can hold it: the code itself, then a deterministic check (a gate step), then one "system one"
model check per rule (a fast model that answers one yes/no question about the change), then the project's guide, then
a rule, then this skill's text. Show the exact text to the human; write only what the human approves.
