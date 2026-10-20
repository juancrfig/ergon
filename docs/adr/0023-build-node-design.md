# 0023 · Build node design

Status: accepted (2026-10-20); superseded in part by 0024. Built 2026-10-20; retries and the way back to Split are not.

## Context
Build is the only node whose agent writes code. It runs without the human (ADR 0022), so it must work on any
project's repos without being prepared per stack, and stop rather than guess.

## Decision
- Input, assembled by code: one story (with criterion ids), every repo of the project checked out on the plan's
  branch, every wiki page tagged `convention`, each repo's AGENTS.md if it has one, the Build skill. On a retry, the
  exact Gate error or the failed Inspect criteria.
- One Build agent for every stack: no frontend or backend variants. Skills are loaded lazily from a list once
  specialised skills exist; until then there are none. Anything enforced (criteria, conventions) never depends on
  what the agent chooses to load.
- The agent may use the terminal, with no isolation; the human accepted that risk. It edits code and may run
  commands; it does not run git. Code creates the branches (`plan/<plan id>`), commits and merges.
- Build chooses which of the project's repos a story changes. Whether changes across repos fit together is
  Inspect's concern.
- Output, one of: a change, with a report per criterion; "no change needed", with why per criterion, which Inspect
  still checks; a stop, with its reason, which sends the plan back to Plan.
- Limits: 60 turns and 30 minutes per run. Up to 3 attempts per story (Build, Gate, Inspect); then the plan goes
  back to Plan. Infrastructure failures (provider, network, login) pause and retry; they do not count.
- After a plan is sent back and replaced, code keeps the leading stories the exact comparison (ADR 0021) finds
  unchanged: it moves the plan's branch back to the commit before the first changed story and rebuilds from there.
  One commit per story makes the cut exact.
- The human merges the plan's branch into main.

## Consequences
- A wrong place for a change passes unless a criterion or convention says where it belongs.
- Each convention Inspect checks costs one more judgment per story.
- Built details: code refuses a repo with uncommitted changes, commits as author Ergon, and on a stop or failure
  saves the unfinished diff and resets the repos to their last commit. Hermes' approval of dangerous commands stays
  on: with no one to approve, such a command is expected not to run (not tested yet).
