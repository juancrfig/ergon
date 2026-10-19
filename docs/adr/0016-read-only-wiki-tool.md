# 0016 · Agents read through a read-only wiki tool

Status: accepted (2026-10-19). Supersedes the page selection and the "no working tools" rule of 0008; amends 0010.

## Context
Code showed the agent the whole wiki, or, above 60,000 characters, made it pick pages from the index in a separate
call. Sources over 120,000 characters were cut without telling the human. Hermes's file tools would let the agent
read for itself, but they also write and reach every file on the machine, which breaks ADR 0005.

## Decision
- Every node agent has one toolset: `ergon/wikitool.py`, an MCP server with three read-only tools: `read_page`,
  `search_wiki` and `read_source` (the source in parts of 20,000 characters).
- Code fixes the scope per run in `tool-scope.json`: one wiki's pages and at most one source. The tool reads
  nothing else and writes only its call log (`tool-calls.jsonl`; one per round in Plan).
- The prompt carries the skill, the conventions, the index and the request. The agent reads pages and the source
  itself.
- Code checks the log before it accepts an answer: the whole source was read; every page an edit replaces or deletes,
  and every page an item is classified against, was read; a health check read every page; a story cites only pages
  the planner read.
- The profile holds the entry that starts the tool, set by hand; `gate.require` refuses a run without it.

## Consequences
- No size limit on the wiki or the source; no page-selection call.
- An agent run takes more turns, and its context grows with each page it reads.
- What the agent saw is the prompt file plus the tool log.
- Hermes still adds its own system prompt (about 8,800 characters with any tool), even with `--ignore-rules`. Not
  solved here.
