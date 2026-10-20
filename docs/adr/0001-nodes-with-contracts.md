# 0001 · Ergon is built from nodes with contracts

Status: accepted (2026-10-18); superseded in part by 0022 and 0024

## Context
theSystem grew into a spaghetti of context: nobody can say what each agent has loaded at a given time, or which exact
step it performs. That makes failures hard to explain and time the bottleneck.

## Decision
- Ergon is a set of nodes. A node turns a defined input into a structured output.
- Each node's contract declares its input and output. Nothing else crosses the node's boundary.
- Each node is run by one agent, with its own Hermes profile.

## Consequences
- Humans and agents improve one node at a time, against its contract.
- The first nodes: Intake, Plan, Split, Build, Gate, Inspect, Merge, Learn. The human approves at Plan and Learn.
