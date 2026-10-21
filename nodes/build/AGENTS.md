# Build node

Carries out Split's tasks, one at a time in order, and commits each on the plan's branch. Agent: `builder`
(agents/AGENTS.md), cheap-smart-enough. Decisions: ADR 0023, 0024, 0025, 0030, 0033.

## Input
- `build`: a Split request that is done. `contracts/request.build.json`. Split puts it in the inbox when its tasks
  pass the checks.

## Output
- Per task, in `runs/<id>/<n>-<task id>/`: `result.json` (`contracts/result.json`): a change or no change, with a
  report per criterion. `runs/<id>/built.json` lists each task's outcome and commits. Then the request moves to
  `done/`.
- Or a stop at a task: a design question for the architect. The request moves to `rejected/`; earlier tasks stay
  committed. Sending it back to Split is not built yet.
- Resubmitting a stopped or failed build (`python3 -m ergon submit` with the same `split`) skips the tasks an earlier
  build of it recorded in its `built.json`.

## Who does what
- Code: refuses to start on a repo with uncommitted changes, or one without a verification skill
  (`.agents/skills/verify/SKILL.md` and `FEATURES.md`, ADR 0033); creates or checks out `plan/<plan id>` in every repo
  the tasks name; writes the builder's prompt (the skill, every `convention` page, the verification skill and
  feature map of the task's repos, the story, the criteria, the task, and the current text of every file the task changes or names to read, ADR 0030);
  checks what changed: only the task's files, a change changed something, no change
  changed nothing, every criterion reported (the feature map may change with any task); then checks each
  criterion's proof against the builder's session logs (each command run after its last file edit, its output
  holding the named lines), recording every check in the task folder's `proof.jsonl`, and sends a failed one back
  like any other problem; commits each task, author Ergon. On a stop or failure it saves the
  unfinished diff in the task folder and resets the repos to their last commit.
- Agent: works in the project folder with the terminal and file tools, in yolo mode (no command approvals), and
  the read-only wiki tool. Never runs git.
- Human: nothing. Merges the plan's branch into main when the plan is done.

## Commands
```
python3 -m ergon run build
python3 -m ergon show <id>
```

The belt as a diagram, for humans: `diagrams.md`. Update it when a state or a move changes.
