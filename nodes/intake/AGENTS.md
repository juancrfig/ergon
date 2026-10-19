# Intake node

Keeps the project wiki true. Agent: `wiki-maintainer` (profiles/wiki-maintainer). Decisions: ADR 0003, 0005-0007.

## Input
One JSON request per file on the node's belt (`<project>/.ergon/intake/`). Contracts:
- `ingest`: a new source, by URL or project file. `contracts/request.ingest.json`
- `correct`: a page claim plus evidence that it is wrong or outdated. `contracts/request.correct.json`
- `health-check`: no payload. `contracts/request.health-check.json`

## Output
- `ingest`, `correct`: a proposal (`contracts/proposal.json`): items with citations and a classification, plus page
  edits. It waits in `review/` until the human approves; then code writes the pages, the index and the log, and
  commits the wiki.
- `health-check`: a report in `runs/<id>/report.json`: mechanical findings from code, semantic findings
  (`contracts/health-report.json`) from the agent. Writes nothing.
- Every request ends in `done/` or `rejected/` (reason in `runs/<id>/rejected.txt`). With `reply_to`, a
  `<id>.result.json` lands in that folder.

## Who does what
- Code: request checks, fetching, duplicate detection, the agent's entire context, proposal checks, applying,
  index, log, commit, ledger.
- Agent: drafts items and edits; finds contradictions and weak claims.
- Human: approves or rejects each proposal.

## Commands
```
ergon profile install wiki-maintainer      # once
ergon intake submit request.json
ergon intake run                           # pauses while 3 proposals wait for approval
ergon intake show <id>
ergon intake approve <id>   |   ergon intake reject <id> "reason"
```

Everything the agent saw is in `runs/<id>/*.prompt.md`; everything it answered, in `*.output.txt`.
