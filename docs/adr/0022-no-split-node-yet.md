# 0022 · No Split node until evidence asks for it

Status: accepted (2026-10-20)

## Context
ADR 0001 listed Split between Plan and Build: it would turn stories into tasks, say where in the code each change
goes, and order them. Designing it showed most of that is done twice or not needed yet. Build is a frontier model
with the code in front of it and finds the files anyway. Plan already sizes each story to one capability. Built one
at a time in order, later stories see what earlier ones built, so no dependency graph is needed (ADR 0018, simplest
first).

## Decision
- The nodes are Intake, Plan, Build, Gate, Inspect, Merge, Learn. Plan and Learn are the only interactive nodes;
  everything between them runs without the human.
- A story is the unit of work. Build takes one story at a time, in the plan's order.
- The order of a plan's stories is the build order; a story may depend only on stories before it.
- Anything after Plan that needs the human sends the plan back to Plan (ADR 0021) and counts as an Ergon failure
  for Learn.

## Consequences
- Lost: building stories in parallel, and sizing work against the code before building. A story too big for one
  Build run is a Plan sizing failure.
- Split comes back when Learn shows stories repeatedly failing Build for being too big.
- If Split comes back, the human chose a frontier model with reasoning for it.
- Supersedes the node list of ADR 0001, Split's model class in ADR 0011, and "task" in ADR 0021's id chain, which is
  now plan, story, criterion, change.
