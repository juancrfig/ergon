# 0029. agy can run the node agents

Status: accepted, 2026-10-20

## Context
A full todo-cli trial on the Hermes profiles cost about 257,000 frontier tokens, 80% of them in Build. Nine trials
per eval round is too much for that. Antigravity CLI (agy) runs Gemini 3.8 Flash cheaply and headless, speaks MCP,
and reports tokens.

## Decision
- `ERGON_AGENT` picks who runs every agent call: `hermes` (default, one profile per node) or `agy`. With agy every
  role, the eval client included, runs on one model, `ERGON_AGY_MODEL` (default `gemini-3.8-flash-medium`). The
  eval runner takes `--agent` and `--model`.
- Only `agent._call` changes. Nodes, skills, contracts and code checks are the same for both, so a trial on agy is
  comparable with one on Hermes.
- Each agy call gets a throwaway HOME: the user's login, the ergon tool scoped to the run, and one Ergon agent
  definition, so none of the user's own agy servers, rules or agents reach the call.
- The agent definition lists no built-in tools, so a node keeps only the ergon tool. Build adds agy's command,
  file and search tools, the equivalent of Hermes' terminal and file toolsets.
- Permissions are skipped (`--dangerously-skip-permissions`): headless agy otherwise refuses every MCP call.
- The run folder keeps agy's step stream as `<label>.session.jsonl` and its conversation database. agy does not show
  its system prompt; `<label>.system-prompt.md` holds the agent definition Ergon wrote.

## Consequences
- agy has no turn limit; the 30-minute call timeout is the only ceiling.
- agy's own system prompt is unseen and changes with agy releases; record the agy version with a trial.
- Results on Flash measure Ergon on a cheaper model, not on the Hermes profiles' models.
