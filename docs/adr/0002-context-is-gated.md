# 0002 · Context is a gated resource

Status: accepted (2026-10-18)

## Context
Context is finite and fragile. In theSystem, agents changed their own memory and skills without a gate, so context
drifted, observability was lost, and a misbehaving agent could not be traced back to the reason.

## Decision
- No context is added to or edited in any agent profile without passing a hard gate.
- Node agents run with Hermes memory and user profile off, and cannot edit their own skills.
- Lessons reach a node only through the Learn node, as a proposed profile change the human approves.
- Each profile carries only the skills and tools its node needs (least capability).

## Consequences
- Reading a profile tells you exactly what its agent loads.
- A node cannot remember anything between runs; durable knowledge lives in the wiki or in the profile's skills.
- Improvements are slower, by design: each one passes Learn and the human.
- The gate's mechanism is still to be designed.
