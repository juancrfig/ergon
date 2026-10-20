# 0027 · Run folders keep the whole conversation; compression stays on

Status: accepted (2026-10-20). Amends 0010 and 0019.

## Context
Node agents run with Hermes' context compression on (ADR 0019): when a conversation fills half of the model's
window, a second model rewrites the older turns into a summary and the agent continues from it. The run folder kept
the prompt code wrote, the system prompt and the tool call log, but not the summary. After a compression the agent
decided from text no one could read, so a misbehavior could not be traced to the builder or to the summary.

Turning compression off would remove the problem, at the cost of failing every run that does not fit. A summary
can also be wrong, but no run has compressed yet, so no bad summary has been seen.

## Decision
- Compression stays on. The first message, the prompt code wrote, is never summarized (`protect_first_n: 1`).
- After each agent call, code saves the whole conversation from `hermes sessions export` as
  `<call>.session.jsonl`: one session per line, oldest first. A compressed session continues in a child session,
  so the export follows the parents back to the first one. The summaries compression wrote are in it.
- The quality of summaries is not addressed until a run shows a bad one.

## Consequences
- A run folder shows everything the model saw, compressed or not.
- A wrong summary can still mislead an agent; the run folder shows that it did.
- Run folders grow by the size of their conversations.
