# Intake node

Keeps the project wiki true. Agent: `wiki-maintainer` (profiles/wiki-maintainer). Decisions: ADR 0003, 0005,
0007, 0008, 0010, 0015-0019.

## Input
One JSON request per file on the node's belt (`<project>/.ergon/intake/`). Contracts:
- `ingest`: a source file inside the project; a `note` can report a wrong claim, with the source as evidence.
  `contracts/request.ingest.json`
- `health-check`: no payload. `contracts/request.health-check.json`

## Output
- `ingest`: a proposal (`contracts/proposal.json`): items with citations and a classification, plus page
  edits. It waits in `review/` until the human approves; then code writes the pages, the index and the log, and
  commits the wiki.
- `health-check`: a report in `runs/<id>/report.json`: mechanical findings from code, semantic findings
  (`contracts/health-report.json`) from the agent. Writes nothing.
- Every request ends in `done/` or `rejected/` (reason in `runs/<id>/rejected.txt`).

## Who does what
- Code: request checks, reading the source, the agent's prompt and tool scope, proposal checks, applying, index,
  log, commit.
- Agent: reads the pages it needs through the wiki tool (ADR 0016); drafts items and edits; finds
  contradictions and weak claims.
- Human: approves or rejects each proposal.

## Commands
```
hermes profile create wiki-maintainer --no-skills --no-alias   # once; then set its model and credentials:
hermes -p wiki-maintainer model                     # code applies the rest (profiles/hermes.yaml)
python3 -m ergon submit request.json
python3 -m ergon run intake                         # drafts a proposal for every queued request
python3 -m ergon show <id>
python3 -m ergon approve <id>   |   python3 -m ergon reject <id> "reason"
```

What the agent was given is in `runs/<id>/*.prompt.md`; what it read, in `tool-calls.jsonl`; what it answered, in
`*.output.txt`.

Diagrams: `diagrams.md`. Update them with every change to this node.
