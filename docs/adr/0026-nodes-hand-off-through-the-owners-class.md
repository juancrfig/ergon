# 0026 · Nodes hand off work through belts and read each other only through the owner's class

Status: accepted (2026-10-20). Updates 0018 and 0019.

## Context
ADR 0018 started from "nodes do not send each other requests yet". Since ADR 0024 they do: approving a plan puts a request on
Split's belt, and a finished split puts one on Build's. Split and Build also read Plan's and Split's files by
hard-coded paths, and imported each other inside functions to avoid import cycles. A housekeeping pass found more
that solved problems Ergon does not have.

## Decision
- A node sends work with `Node.hand_off(node, request)`: code builds the request and puts it on the other node's
  belt; that node checks it when it runs. A node reads another node's output only through that node's class:
  `Plan.approved(plan)`, `Split.tasks(split)`.
- Shared pieces live with their owner: story text and criterion ids in `plan.py`, the project's repos in `node.py`,
  convention pages in `wiki.py`.
- Build resumes from its own records (`built.json`), not from git commit messages.
- The system prompt in each run folder comes from `hermes sessions export`, Hermes' supported interface, not from
  its private session database. The `database.journal_mode` setting that only served that read is dropped.
- The wiki has no `log.md`: nothing read it, and the wiki's commits are its history.
- `python3 -m ergon install` replaces the shell installer: one language, one entry point.
- Reading a belt no longer creates its folders; only `install` and `put` do.
- The Hermes profile module is `profiles.py`, not `gate.py`: Gate is a factory node.

## Consequences
- Intake, Plan, Split and Build behave as before; only the code paths moved.
- Without git commit scanning, a task committed by a build that crashed before writing `built.json` is built again.
