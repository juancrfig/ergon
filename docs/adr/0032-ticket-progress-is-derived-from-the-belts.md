# 0032. Ticket progress is derived from the belts

Status: accepted, 2026-10-21. Builds on ADR 0003, 0014 and 0021.

## Context
Work usually arrives as a ticket from a tracker (a Jira issue, for example). Ergon had no ticket: a plan request
held the goal as free text, a split request pointed at its plan and a build request at its split. Nothing tied the
chain to the ticket, a replaced plan started a new chain, and seeing progress meant looking up one request per belt.

## Decision
- A ticket is an id the human gives on the plan request (`ticket`): the tracker's key or a local one. A plan that
  replaces a rejected one uses the same ticket.
- Only the plan request names the ticket. Split and build requests reach it through their links (build → split →
  plan); they do not copy it.
- A ticket's tasks are the tasks Split cut from its newest approved plan.
- No ticket record is stored. `ergon ticket <id>` reads the belts: request states from their folders,
  tasks from Split's run folder, task outcomes from Build's, time and tokens from each task's call log. Fixed rules
  give one status: planning, waiting for your answers or approval, plan rejected, splitting, split stopped,
  building k of n, build failed, done. `ergon ticket` lists every ticket with its status.

## Consequences
- The view cannot disagree with the belts: there is nothing else to keep in sync.
- Every query reads the belts; this stays fast because belt files are small (run-folder growth is issue #68).
- The ticket's source text goes to the wiki through Intake, as any document; Ergon does not sync with the tracker.
