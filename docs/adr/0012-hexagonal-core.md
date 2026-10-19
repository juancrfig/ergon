# 0012 · The core knows no interface

Status: accepted (2026-10-18)

## Context
Humans and agents will reach ergon through different interfaces over time: a terminal, a chat app, another agent.
If a node depends on one of them, replacing it means rewriting the node.

## Decision
- Ergon is hexagonal. The core (nodes, contracts, belts) exposes ports; interfaces are adapters at the edge.
- Every interaction with a node, including the human's answers and approvals, is a JSON file on its belt, valid
  against a contract. The command line is the first adapter, and it only reads and writes those files.
- No node depends on a chat app, a TTY or an interactive session.

## Consequences
- A new interface is a new adapter; no node changes.
- Conversations become request and response files, so every exchange is recorded and measurable.
