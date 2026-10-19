# 0008 · Code assembles the agent's entire context

Status: accepted (2026-10-18)

## Context
ADR 0002 makes context a gated resource. If an agent loads skills, memory or project files itself, or opens pages
with tools, nobody can say afterwards what it saw.

## Decision
- A node's runner builds the agent's whole prompt from repo files and project data: the skill for the request type,
  the conventions, the index, the pages, the request and the source. Hermes adds nothing (`--ignore-rules`).
- The wiki-maintainer gets no working tools. When the wiki is too large to show whole, it first returns the pages it
  needs (a contract of its own), and code loads them.
- Each prompt and each answer is saved in the request's run folder.
- A profile in the repo is `config.yaml` (installed verbatim) plus `skills/*.md` (read by the runner, one per
  request type). The installed Hermes profile holds no skills and no memory.
- Ergon uses only the Python standard library, including its own JSON Schema subset.

## Consequences
- Any agent decision can be explained from one file: the prompt it received.
- A large wiki costs one extra model call per request.
- ADR 0005's "any agent reads the wiki directly" now means: reading needs no request; code places the pages an agent
  needs in its context.
