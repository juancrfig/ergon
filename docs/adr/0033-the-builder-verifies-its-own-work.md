# 0033. The builder verifies its own work

Status: proposed, 2026-10-21. Design in progress; not built. Supersedes the Inspect node of the factory design.

## Context
The builder never sees its code run: the Build skill forbids servers, no project gives it a way to drive the app,
and checking was left to Gate and an Inspect agent after the fact. Following poteto's "verification is all you
need": an agent verifies its own work by driving the real app, through a small agent-friendly tool the project
owns, and attaches proof.

## Decided so far
- Each project has a verification skill: how to start, drive and inspect its app, with a feature map (what the app
  does and how to reach each feature, navigation only). Both live in the repo next to the tool; the builder that
  changes a feature updates the map in the same commit. Requirements stay in the wiki and Plan's stories.
- A wizard skill Ergon ships creates them; the human runs it once per project with a coding agent, interactively,
  reviews and commits the result. Ergon does not run it as a ticket.
- Build refuses to start a ticket's first task while the project lacks the verification skill or the feature map:
  a deterministic file check, no fallback.
- The builder's context is minimal: the Build skill, Split's hand-off (task, criteria, files to change and read),
  the verification skill and the wiki's convention pages. Repo AGENTS.md files are maps for finding files; they go
  to Split, which explores, not to the builder, which is handed its files (done, with this ADR).
- The Build skill keeps only rules with evidence or a safety purpose: change only the listed files and remove files
  checks create; stay inside the project, no installs; stop on an open design decision. Added for
  verification: prove each covered criterion through the verification skill before answering; start and stop the
  app only through it and stop what you started; stop when it cannot drive what a criterion needs.
- Proof: per covered criterion, the steps the builder ran; a step is a command, the repo it runs in, the exit code
  it expects and the lines its output must contain. Code replays every step in a clean copy of the repos at the
  commit; a step passes when the exit code matches and every named line appears, so dates, ids and timings
  elsewhere in the output do not break it. No Inspect agent; a light judge only if a project gets criteria that cannot be re-run.
- Gate (compile, type check, lint) stays as the deterministic floor.

## Open
- Where the proof is stored.
- The verification tool's interface rules and the wizard's steps.
- Environment: seed data, ports, cleanup between tasks, who installs dependencies.
- Where a project declares its Gate checks.
- Measuring: do builder proofs agree with hidden tests, and a web case to measure the tool.
