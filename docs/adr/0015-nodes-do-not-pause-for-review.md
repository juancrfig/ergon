# 0015 · Nodes do not pause for review

Status: accepted (2026-10-19)

## Context
Intake stopped drafting while 3 proposals waited for approval, and Plan while 3 plans waited for the human. The
human runs every node by hand (ADR 0014) and decides when to review, so the pause only delayed work he had asked for.

## Decision
- `ergon run intake` and `ergon run plan` work every queued request, however many wait for the human.

## Consequences
- Proposals drafted against the same wiki can overlap. Approving one changes the wiki, so the others fail the
  fingerprint check at approval and must be submitted again.
