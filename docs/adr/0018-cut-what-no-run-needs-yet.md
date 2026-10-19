# 0018 · Cut what no run needs yet

Status: accepted (2026-10-19). Supersedes the `correct` request type and URL sources of 0005.

## Context
Nothing has run with a real model. A housekeeping review found features built for situations that have not
happened: nodes do not send each other requests yet (ADR 0014: the human runs each node), and the human approves
every wiki change.

## Decision
- No `reply_to` result files. The human reads results with `show` and `pending`.
- No `correct` request type. A wrong claim is an `ingest` whose `note` names the page and the claim; the source is
  the evidence. The skill tells the agent to read that page first.
- Sources are project files only. Ergon fetches no URLs: the human saves a web page or pasted text to a file
  first. No HTML conversion, no network step, no internet text arriving unseen.
- No ledger of ingested sources. The human sees a repeated source when approving its proposal.

## Consequences
- Less code and fewer contracts to keep in sync.
- Each cut comes back through a new ADR when a real run needs it: `reply_to` when nodes chain, URLs when saving
  files by hand costs too much, the ledger when duplicates reach review.
