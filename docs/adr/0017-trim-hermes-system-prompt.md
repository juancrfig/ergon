# 0017 Trim Hermes' own system prompt and record it per run

Status: accepted. Modifies 0010 and 0016.

## Context
Even with `--ignore-rules` and only the wiki tool, Hermes sends about 8,800 characters of its own system prompt. Most
of it is for a coding agent: read and edit files, run tests and builds, do not commit unless asked, finish the job,
a git snapshot of the working directory, and terminal formatting. A node agent is read-only and answers in JSON, so
these instructions contradict its job. The text was not in the run folder either.

Hermes exposes settings for each of these sections (`agent.*`, `platform_hints`). A probe on a real profile showed
the prompt drop to about 2,900 characters with the same answer and the same tool calls.

## Decision
- Every node profile carries `gate.PROMPT_SETTINGS`: coding context off, task completion, parallel tool call, tool
  use and execution guidance off, no environment probe or bot protocol, and the terminal hint replaced by "Code
  reads your final answer, not a person." Tool search is off: with it on, Hermes hid the wiki tool behind three
  lookup tools (`tool_search`, `tool_describe`, `tool_call`), which costs turns. The wiki tool entry turns MCP
  resource and prompt helpers off. `gate.require` refuses a run when any line is missing.
- After each agent call, code copies the system prompt Hermes stored for that session into the run folder
  (`<call>.system-prompt.md`). A call whose prompt cannot be found fails.

## Consequences
- Still sent, and accepted: Hermes' identity line ("You are Hermes Agent..."), the Hermes help note, the mid-turn
  steering note, the active profile note, the date and model, and host details. About 2,900 characters.
- The run folder now holds everything the model saw: the system prompt, the prompt code wrote, and the tool log.
- A Hermes upgrade can add new sections; the recorded system prompt shows them.
