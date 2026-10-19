# 0009 · Documentation for agents lives in AGENTS.md files

Status: accepted (2026-10-18)

## Context
Agent harnesses load AGENTS.md files automatically; they do not load READMEs. Documentation an agent never loads
does not exist for it, and two kinds of docs per folder double what has to stay true.

## Decision
- The repository has one README, at the root, for humans.
- Every other folder explains itself in an AGENTS.md, for the agents that maintain ergon.
- AGENTS.md files stay short, because each one lands in the context of every agent working in its folder.

## Consequences
- Maintainer agents see the folder structure without being told where to look.
- Node agents are not affected: their runs skip AGENTS.md (ADR 0008).
