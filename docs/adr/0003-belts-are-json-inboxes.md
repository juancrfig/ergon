# 0003 · Belts are inbox folders of JSON requests

Status: accepted (2026-10-18)

## Context
Nodes need a way to send each other work. A2A would add running services, authentication and network failures.

## Decision
- Each node has an inbox folder. One request is one JSON file.
- Each request type has a JSON Schema: the schema is the contract.
- A script, not a model, checks each request against its schema on arrival and rejects malformed ones with a reason.
- Requests move between folders as they progress: inbox, working, then done (with a link to the output) or rejected
  (with the reason).
- Large content is a separate file that the request points to.

## Consequences
- The number of waiting files is the queue length, which gives backpressure.
- The done folder is the node's history.
- A2A is deferred until a node runs on another machine.
