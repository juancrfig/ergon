---
name: verification-heuristics
description: Use when designing, creating or judging how agents verify their work, or when a project has no verification guide. Holds the tenets, proof standards and the wizard that creates a project's guide.
---

# Verification heuristics

The philosophy every verification system in this workspace follows, plus the wizard that turns it into one
project's verification guide. Tenets are general on purpose; each project's guide makes them concrete.
The human approves every change to this skill.

## Tenets

1. **Take the deterministic parts out of the LLM's responsibilities; what you cannot make deterministic, at least
   make the decision narrow.**
   Why: three LLM readings missed a missing quote that a compiler catches in seconds, every time. A model judging one
   rule at a time decides more reliably than one reviewer holding every rule at once.

2. **Use triggers to pull information back into the loop, so the human does not bottleneck the system by having to.**
   Why: when no trigger brings a failure back to the agent, the human becomes the trigger, a meat proxy between the
   agent and reality.

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

- Evidence runs leave proof, not code. Writing or changing automated tests stays under
  `rules/tests-and-verification-need-human-approval.md` until a test protocol exists.
- Helper scripts a guide ships are code in the company's repository: the human approves them like any change.
- Agents touch a real data source only with the access the guide records for it. The human sets that access.
- Running the app, builds or checks still needs the human's explicit ask (same rule). Asking for the wizard, or for
  an evidence run, is that ask.

## How this skill grows

Every verification failure comes with a proposal that prevents it from happening again. Place the fix at the
strongest layer that can hold it: the code itself, then a deterministic check, then one "system one" model check
per rule (a fast model that answers one yes/no question about the change), then the project's guide, then a rule,
then this skill's text. Show the exact text to the human; write only what the human approves.
