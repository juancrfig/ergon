# 0016 · Agents read through a read-only wiki tool

Status: accepted (2026-10-19). Supersedes the page selection and the "no working tools" rule of 0008; amends 0010.

## Context
Code showed the agent the whole wiki, or, above 60,000 characters, made it pick pages from the index in a separate
call. Sources over 120,000 characters were cut without telling the human. Hermes's file tools would let the agent
read for itself, but they also write and reach every file on the machine, which breaks ADR 0005.

## Decision
- Every node agent has one toolset: `ergon/wikitool.py`, an MCP server with two read-only tools: `search_wiki` and
  `read_pages` (several pages in one call, so reading takes one or two turns).
- Code fixes the scope per run in `tool-scope.json`: one wiki's pages. The tool reads nothing else and writes only
  its call log (`tool-calls.jsonl`; one per round in Plan).
- The prompt carries the skill, the conventions, the index, the request and the whole source, never cut. A source
  too big for the model fails the run visibly.
- Code does not check what the agent read. The agent is trusted to read a page before it replaces it; the tool's
  limits, the proposal checks, the fingerprint check and the human's approval stay. A latent issue tracks stricter
  checks, to build only after a real case.
- The profile holds the entry that starts the tool, set by hand; `gate.require` refuses a run without it.

## Consequences
- No size limit of ergon's own on the wiki or the source; no page-selection call.
- An agent run takes one or two more turns than when code loaded the pages.
- What the agent saw is the prompt file plus the tool log.
- A replacement written without reading the page can drop content; the approval screen shows only page names. Every
  approval is a commit, so the loss can be undone.
- Hermes still adds its own system prompt (about 8,800 characters with any tool), even with `--ignore-rules`. Not
  solved here.
