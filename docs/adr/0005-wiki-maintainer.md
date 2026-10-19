# 0005 · The wiki-maintainer is the only wiki writer

Status: accepted (2026-10-18)

## Context
The Intake node keeps the project wiki current. Several agents learn things the wiki should hold.

## Decision
- The Intake node is run by the wiki-maintainer. It is the only agent that writes the wiki.
- Any agent reads the wiki directly; reading needs no request.
- Request types: `ingest` (a new source), `correct` (evidence that a wiki claim is wrong or outdated) and
  `health check` (a report; writes nothing).
- The wiki-maintainer has no tools to execute code.

## Consequences
- Write access to the wiki is enforced by access, not by instructions.
- Resolving a contradiction is a `correct` request whose sender is the human.
