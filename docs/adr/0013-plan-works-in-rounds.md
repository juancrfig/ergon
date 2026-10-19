# 0013 · Plan works in rounds of JSON questions and ends in stories

Status: accepted (2026-10-18)

## Context
Planning is a conversation with the human, but a node takes a defined input and gives a structured output, and the
core knows no interface (ADR 0012). Planning quality is also the thing theSystem could not measure.

## Decision
- Input: a `plan` request holding the human's goal. Documents (requirements, transcripts) go through Intake first;
  the planner reads only the wiki.
- Each round the planner returns either questions (each with options, a recommendation and why it matters) or the
  final stories. Questions wait in `waiting/` for the human's answers file; a skipped question takes the
  recommendation. Stories wait in `review/` for approval.
- A story has a title, as a / I want / so that, observable `done_when` criteria, `out_of_scope`, and the wiki pages
  it rests on. Inspect checks `done_when`.
- At most 5 rounds: the last one must return stories.

## Consequences
- Every exchange is a file, so each plan records rounds, questions per round, skipped questions, how often the
  human took the recommendation, and rejected stories.
- Planning a goal whose sources are not in the wiki first needs an Intake pass and its approvals.
