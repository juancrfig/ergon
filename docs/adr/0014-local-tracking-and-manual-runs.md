# 0014 · Belts are the record; runs are started by hand

Status: accepted (2026-10-18)

## Context
The human needs to see queues, what waits for them, and node metrics, without a chat app or a database.

## Decision
- Nodes run only when the human starts them (`ergon run <node>`). No scheduler, no dispatcher.
- The belt folders are the state. Each belt appends every move to `events.jsonl`; nothing else records history.
- One command line for every node: `submit` routes by request type; `pending`, `show`, `answer`, `approve` and
  `reject` find the node by request id.
- Metrics come from the event log and the run folders: time working vs. waiting for the human, first-pass rate (no
  contract retry, no rejection), and queue length.

## Consequences
- Nothing moves while the human is away.
- A metrics report is still to be written; the data is recorded from the first request.
