# 0021: Plans are replaced, never edited

Status: accepted (2026-10-19); superseded in part by 0022 and 0024. Not built yet: the first real change to an approved plan, or Build, builds it.

## Context

Later nodes cite a story's acceptance criteria by `<story id>#<n>`, its 1-based position. Editing an approved plan
would shift positions and make those citations point at the wrong criterion, silently.

## Decision

- An approved plan never changes. A change (a story removed, updated or added) is a new plan that names the plan it
  replaces; the planner gets the old stories and the human's change, and returns the whole new set.
- Code compares the two plans exactly, with no model: stories by id (in both, added, removed); criteria by exact
  text within a story. An edited criterion shows as removed plus added. Every criterion of the new plan is
  identical to an old one or shown to the human before approval.
- A plan is the group of stories for one goal and works as the ticket; there is no separate ticket.
- Work (plans, tasks, changes) lives on the nodes' belts in the project, linked by ids: plan, story, criterion,
  task, change. The wiki holds facts only; a fact a merged change makes true reaches it through Intake.
