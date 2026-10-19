# Intake node

Keeps the project wiki true. Agent: `wiki-maintainer` (profiles/wiki-maintainer). Decisions: ADR 0003, 0005, 0007, 0008, 0010, 0015, 0016.

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
- Code: request checks, fetching, duplicate detection, the agent's prompt and tool scope, proposal checks (including
  what the agent read), applying, index, log, commit, ledger.
- Agent: reads the source and the pages it needs through the wiki tool (ADR 0016); drafts items and edits; finds
  contradictions and weak claims.
- Human: approves or rejects each proposal.

## Commands
```
hermes profile create wiki-maintainer --no-skills   # once; set its model and add the wiki tool by hand (the
                                                    # first run prints the config entry if it is missing)
python3 -m ergon submit request.json
python3 -m ergon run intake                         # drafts a proposal for every queued request
python3 -m ergon show <id>
python3 -m ergon approve <id>   |   python3 -m ergon reject <id> "reason"
```

What the agent was given is in `runs/<id>/*.prompt.md`; what it read, in `tool-calls.jsonl`; what it answered, in
`*.output.txt`.

Diagrams: `diagrams.md`. Update them with every change to this node.
