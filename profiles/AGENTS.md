# Profiles

One card per node agent. This file is the only place that says what each agent gets: model class, skills, tools,
the context code writes, and the context Hermes adds. Anything not listed here does not reach the model. When a
profile changes, change its card in the same commit.

`profiles/<name>/skills/` holds the agent's skills. A change there reaches the agent only through a commit the human
approves (ADR 0002). The Hermes profile of the same name (`~/.hermes/profiles/<name>/config.yaml`) holds only what
"Hermes profile" below lists.

## The same for every profile

**Hermes profile**:
- Model and credentials: set by hand. Until the human sets them, the model is `SET-BY-HAND` and runs are refused.
- Everything else: `profiles/hermes.yaml`, the canonical config. Code applies it before each run and it wins over
  hand edits (ADR 0019). It holds the wiki tool entry, the settings that trim Hermes' own system prompt and turn
  tool search off (ADR 0017), Hermes' hard stop for replayed tool calls, context compression set like
  theSystem's main agent (the first message, with the source, never summarized), reasoning kept out of the
  output, memory and telemetry off, and the timezone. Everything else is Hermes' default.

**Tools**: `search_wiki` and `read_pages`. Read-only, scoped by code to one wiki per run (ADR 0016). Every run passes
`-t ergon`, so no other toolset loads; tool search is off, so the model sees the two tools directly, not behind
lookup tools.

**Skills**: code reads the agent's skill file and puts it first in the prompt, once per call. The agent never picks
one. Hermes loads none of its own (`--no-skills`, `--ignore-rules`).

**Context Hermes adds**, about 2,900 characters, accepted in ADR 0017:
- Identity: "You are Hermes Agent, built by Nous Research. Be direct..."
- A note on where Hermes' own docs are.
- The mid-turn steering note: how a user message arrives during a run. No user sends one in Ergon.
- "Code reads your final answer, not a person." It replaces the terminal formatting hint.
- The active profile and its folders.
- Date, model, provider and platform.
- Host, home folder, working directory and scratch folder.

**Not added**, by `--ignore-rules` and the settings: SOUL, AGENTS.md, memory, Hermes' skill list, plugin sections,
coding-agent instructions, the workspace git snapshot.

**Evidence per run**, in the run folder: `<call>.system-prompt.md` (what Hermes added, copied from its session
store), `<call>.prompt.md` (what code wrote), the tool call log, and `<call>.output.txt` (the answer).

**How to check a profile**: read `profiles/hermes.yaml`; it is what the profile gets. After a run, compare
`<call>.system-prompt.md` with the list above. Anything extra came with a Hermes upgrade and needs a setting or an
ADR.

## wiki-maintainer (Intake)

- **Model class**: cheap-smart-enough (ADR 0011).
- **Skills**, one per call, picked in `ergon/intake.py` `_context`:
  - `wiki-maintenance`: an `ingest` request is drafted into a proposal.
  - `health-check`: a `health-check` request runs and the wiki has more than one page.
- **Context code writes**: the skill, the wiki conventions, the index, the request, the whole source (for
  `ingest`), and the answer contract.
- **Answer contract**: `nodes/intake/contracts/proposal.json` or `health-report.json`.

## planner (Plan)

- **Model class**: frontier-reasoning (ADR 0011).
- **Skills**, picked in `ergon/plan.py` `_context`:
  - `planning`: every round of a plan, whether it ends in questions or stories.
- **Context code writes**: the skill, the index, the goal, earlier rounds with the human's answers, the round
  number, and the answer contract.
- **Answer contract**: `nodes/plan/contracts/round.json`.
