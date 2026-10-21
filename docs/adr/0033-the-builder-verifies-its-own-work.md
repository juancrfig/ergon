# 0033. The builder verifies its own work

Status: accepted, 2026-10-21. The wizard skill is not written yet. Supersedes the Inspect node of the factory design.

## Context
The builder never sees its code run: the Build skill forbids servers, no project gives it a way to drive the app,
and checking was left to Gate and an Inspect agent after the fact. Following poteto's "verification is all you
need": an agent verifies its own work by driving the real app, through a small agent-friendly tool the project
owns, and attaches proof.

## Decided so far
- Each source clone has a verification skill in `<clone>/.agents/skills/verify/` (the standard agent-skills
  place, so the human's own coding agents find it too): `SKILL.md`, `FEATURES.md` and the tool if the app needs one.
  It holds how to start, drive and inspect its app, with a feature map (what the app
  does and how to reach each feature, navigation only). Both live in the repo next to the tool; the builder that
  changes a feature updates the map in the same commit; code accepts FEATURES.md with any task's files. Requirements stay in the wiki and Plan's stories.
- A wizard skill Ergon ships creates them; the human runs it once per project with a coding agent, interactively,
  reviews and commits the result. Ergon does not run it as a ticket.
- Build refuses to start a ticket's first task while any source clone its tasks touch lacks `SKILL.md` or
  `FEATURES.md`:
  a deterministic file check, no fallback.
- The builder's context is minimal: the Build skill, Split's hand-off (task, criteria, files to change and read),
  the verification skill and the wiki's convention pages. Repo AGENTS.md files are maps for finding files; they go
  to Split, which explores, not to the builder, which is handed its files (done, with this ADR).
- The Build skill keeps only rules with evidence or a safety purpose: change only the listed files and remove files
  checks create; stay inside the project, no installs; stop on an open design decision. Added for
  verification: prove each covered criterion through the verification skill before answering; start and stop the
  app only through it and stop what you started; stop when it cannot drive what a criterion needs.
- Proof: per covered criterion, the commands the builder ran and the lines their output showed. Code checks each
  against the session logs of the task's calls, which already record every command and its output: the same
  command, run after the builder's last file edit, whose output holds every named line. Dates, ids and timings
  elsewhere do not matter. Nothing is run again, so the check adds no time. agy's log has no exit code, so an exit
  code is proved by printing it (`; echo "exit $?"`). A failed check goes back to the builder like any other
  problem; every check is recorded in the task folder's `proof.jsonl`.
- Rejected: replaying each proof in a clean copy of the repos. It also catches a proof that held only because of a
  file outside the change, but runs every proof twice, which costs minutes per task once proofs start servers.
  It comes back if evals show proofs passing on leftover files. Not caught either: an edit made through a shell
  command after the proof, since only file tools count as edits.
- No Inspect agent; a light judge only if a project gets criteria that cannot be re-run.
- Gate (compile, type check, lint) stays as the deterministic floor.

## Open
- The verification tool's interface rules and the wizard's steps.
- Environment: seed data, ports, cleanup between tasks, who installs dependencies.
- Where a project declares its Gate checks.
- Measuring: do builder proofs agree with hidden tests, and a web case to measure the tool.
