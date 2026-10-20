# Split node

Turns an approved plan's stories into tasks a cheap builder carries out with no design decision. Agent: `architect`
(agents/AGENTS.md), frontier-reasoning. Decisions: ADR 0024, 0025.

## Input
- `split`: an approved plan. `contracts/request.split.json`. Approving a plan puts this request in the inbox.

## Output
- `contracts/tasks.json`, in `runs/<id>/tasks.json`: the tasks in build order, then the request moves to `done/`.
  No human approves them.
- Or a stop: a product question the stories leave open. The request moves to `rejected/` with the reason and the
  question; the human submits a new plan by hand. Sending it back to Plan (ADR 0021) is not built yet.

## Who does what
- Code: the request check, the architect's prompt (the skill, every wiki page tagged `convention`, the wiki index,
  the stories with criterion ids, the file listing of every repo) and tool scope, and the task checks: unique ids,
  every criterion covered, every task covers real criteria, repos exist, a changed or deleted file exists, a created
  one does not.
- Agent: reads code and wiki through the read-only tool (ADR 0016, 0025); designs the tasks, or stops.
- Human: nothing. A stop reaches the human through Plan.

## Commands
```
python3 -m ergon run split
python3 -m ergon show <id>
```

The belt as a diagram, for humans: `diagrams.md`. Update it when a state or a move changes.
