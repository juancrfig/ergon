# 0015 · Intake does not pause for review

Status: accepted (2026-10-19)

## Context
Intake stopped drafting while 3 proposals waited for approval. The human runs every node by hand (ADR 0014) and
decides when to review, so the pause only delayed drafts he had already asked for.

## Decision
- `ergon run intake` drafts a proposal for every queued request, however many wait for approval.

## Consequences
- Proposals drafted against the same wiki can overlap. Approving one changes the wiki, so the others fail the
  fingerprint check at approval and must be submitted again.
- Plan keeps its own limit; this decision covers Intake only.
