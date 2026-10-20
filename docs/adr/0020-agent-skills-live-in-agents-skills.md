# 0020: Agent skills live in agents/skills/

Status: accepted (2026-10-19)

## Context

Skills lived per profile in `profiles/<name>/skills/`, next to the canonical Hermes config and the profile cards.
Global configuration for agents should stay simple: Ergon needs skills now and nothing else. Project facts and
conventions belong in the project wiki, where they have a source and the human's approval; a skill guides how an
agent works and is never a requirement a node checks.

## Decision

- Global agent configuration is skills only: `agents/skills/<skill>.md`, one file per skill, one flat folder shared
  by every agent and project. Each node's code names the skills its agent gets.
- `agents/AGENTS.md` keeps one card per node agent: what it gets.
- The canonical Hermes config moves to `ergon/hermes.yaml`: code applies it, so it lives with the code. ADR 0019
  holds otherwise.
- Scripts, MCP servers or other agent configuration get a place when a run needs them, not before.

## Consequences

- A new node adds its skills to `agents/skills/` and names them in its code; no folder per profile.
- Earlier ADRs that name `profiles/` paths describe the old layout.
