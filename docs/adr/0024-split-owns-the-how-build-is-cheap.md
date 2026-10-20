# 0024 · Split owns the how; Build is cheap

Status: accepted (2026-10-20)

## Context
ADR 0022 dropped Split assuming a frontier Build that decides how to change the code. The human chose a cheap,
smart-enough model for Build: a Build mistake must trace to an upstream gap, not to Build's judgment. Stories state
what the user sees and nothing about how, so with stories alone nobody upstream owns the design.

## Decision
- The nodes are Intake, Plan, Split, Build, Gate, Inspect, Merge, Learn. Plan owns the what, Split the how, Build
  carries it out. Plan and Learn are the only interactive nodes.
- Split runs on a frontier model with reasoning. It reads every repo of the project (read-only), the wiki and every
  `convention` page, and turns a plan's stories into tasks.
- A task is detailed enough that a cheap model makes no design decision: its repos and files, the pieces to create
  or change, their interfaces and data shapes, and the criteria it covers. No code.
- Tasks run in Split's list order, one commit per task on the plan's branch; a task depends only on tasks before
  it. No dependency graph.
- Code checks Split's output: every criterion is covered by a task, every task covers a criterion, every listed file
  exists unless the task creates it, every repo exists.
- A product doubt stops Split and sends the plan back to Plan. A design doubt stops Build and sends the story back to
  Split, which redoes its tasks with the doubt; after 3 tries the plan goes back to Plan. Each is a failure of the
  node upstream, recorded for Learn.
- Build runs on a cheap, smart-enough model and takes one task at a time instead of one story. Its repos are the
  task's. The rest of ADR 0023 holds.

## Consequences
- Supersedes ADR 0022, and in ADR 0023 Build's input, model class and choice of repos. In ADR 0011, Split is
  frontier-reasoning and Build cheap-smart-enough. ADR 0021's id chain is plan, story, criterion, task, change.
- After a replaced plan, the cut of ADR 0023 falls before the first task of the first changed story.
