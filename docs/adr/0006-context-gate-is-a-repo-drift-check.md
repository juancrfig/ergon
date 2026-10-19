# 0006 · The context gate is a repo drift check

Status: superseded by 0010

## Context
ADR 0002 requires a hard gate before any context reaches an agent profile, and left the mechanism open.

## Decision
- Profiles are defined only in the ergon repo. A profile changes only through a commit the human approves.
- Before every run, a script compares the installed profile with the repo. On any difference the run does not start,
  and the human is told what differs.
- Node agents have no tools that write memory or skills.

## Consequences
- Drift is detected before a run, not discovered after a failure.
- Locking profiles at the operating-system level (a separate user without write access) is deferred until the repo
  check proves insufficient.
