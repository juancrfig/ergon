# 0028. The plan's decisions go into the wiki before its stories are approved

Status: accepted, 2026-10-20

## Context
The first eval trial stopped at Split. The wiki said removing an item deletes it for good, with recoverability still
open. The client then decided that removed items can be restored. That answer lived only in the plan, so the approved
stories contradicted the wiki, and Split stopped on the conflict, as its skill tells it to. Letting stories win over
the wiki would have left the wiki stale for every later plan.

## Decision
- The human's answers to the planner are decisions about the project, and the wiki is where decisions live.
- When the planner returns stories after at least one answered round, code saves every round's questions and answers
  as a source in `wiki/raw/` and hands Intake an ingest request for it. Plan never calls Intake's agent and never
  waits on it (ADR 0026): the request waits in Intake's inbox.
- Approving the plan applies Intake's wiki change first, then approves the stories. One approval covers both. Plan
  refuses the approval while the change is not drafted, when Intake rejected it, or when the wiki changed after the
  draft (Intake's own check).
- Rejecting the plan rejects its pending wiki change.
- The planner does not write a story that contradicts the wiki unless an answer decided it; Split still stops on a
  contradiction it finds, as the safety net.

## Consequences
- One more Intake run per plan with answered rounds, and no more approvals for the human.
- A rejected wiki change blocks the plan: the human sees why and plans again.
- Whether a story contradicts the wiki stays a model judgment; code checks only that the decisions reached the wiki.
