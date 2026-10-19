# Profiles

One folder per node agent, holding only `skills/*.md`. A change here is a change to an agent's context: it reaches
the agent only through a commit the human approves (ADR 0002).

The Hermes profile of the same name holds only the model, credentials, the entry that starts the wiki tool and the
settings that trim Hermes' own system prompt (ADR 0017), set by hand; `gate.require` prints what is missing. Nothing else in it reaches the model (ADR 0010, 0016).

## Skills in use

This is the only list. A skill not listed here is not loaded. Code picks the skill; the agent never chooses one.

| Agent | Node | Skill | Loaded when | Picked in |
|---|---|---|---|---|
| wiki-maintainer | Intake | `wiki-maintainer/skills/wiki-maintenance.md` | an `ingest` or `correct` request is drafted into a proposal | `ergon/intake.py`, `_context` |
| wiki-maintainer | Intake | `wiki-maintainer/skills/health-check.md` | a `health-check` request runs and the wiki has more than one page | `ergon/intake.py`, `_context` |
| planner | Plan | `planner/skills/planning.md` | every round of a plan, whether it ends in questions or stories | `ergon/plan.py`, `_context` |

How a skill is loaded:
- Code reads the file and puts it first in the prompt, once per agent call. The prompt is saved in the run folder
  as `*.prompt.md`.
- Hermes loads no skills of its own: profiles are created with `--no-skills`, and every run passes `--ignore-rules`.

When you add, rename or remove a skill, change this table in the same commit.
