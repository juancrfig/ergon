# 0004 · One ergon per project; profiles are shared

Status: accepted (2026-10-18)

## Context
An agent that handles several projects must switch between project contexts.

## Decision
- Ergon handles one standalone project, with its own wiki. Requests carry no project field.
- A node's profile is the same for every project. The project comes from where the run starts.

## Consequences
- No run ever sees two projects.
- Improving a profile once improves it for every project.
- Project knowledge lives in the project's wiki, never in a profile.
