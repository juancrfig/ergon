# 0007 · Wiki writes wait for human approval

Status: accepted (2026-10-18)

## Context
Other nodes treat the project wiki as ground truth, so a wrong write spreads to every node that reads it.

## Decision
- The wiki-maintainer's output for `ingest` and `correct` is a proposal. Code writes it to the wiki only after the
  human approves it as a whole.
- `health check` writes nothing, so it needs no approval.
- Each step goes to whoever does it reliably: code does everything with one right answer (request and proposal
  checks, fetching, applying edits, index, log, commit, ingest ledger); the model drafts and classifies, and returns
  JSON that code checks.

## Consequences
- The wiki-maintainer never touches git.
- When its proposals keep matching the human's decisions, approval can move to sampled checks, through a new ADR.
