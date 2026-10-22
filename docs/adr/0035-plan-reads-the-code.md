# 0035. Plan reads the code

Status: accepted, 2026-10-22.

## Context
Plan read only the wiki. The wiki describes what the product should do, so plans assumed screens and records that
the code did not have. Split read the code, found the gap, and stopped; the ticket went back to Plan, each time
with more rounds of human questions.

## Decision
- Plan gets the same read-only code tools as Split, over the project's repos.
- The planning skill says: check in the code that what the goal and the wiki assume exists; where it does not,
  write a story that builds it. Do not ask the human what the code answers.

## Consequences
- Plan costs more turns per round. It should ask fewer questions and send fewer tickets back from Split.
- Plan sees the working tree as it is when it runs, which can be a branch of a running build.
