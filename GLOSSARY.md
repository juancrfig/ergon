# Ergon glossary

One word per concept. Add a term only when it is decided.

**Ergon**: the factory. A set of nodes that turns raw information into merged, working software.

**Node**: a process that turns a defined input into a structured output. Its contract declares both; nothing else
crosses its boundary.
_Avoid_: module, step, stage, phase.

**Contract**: the declaration of a node's input and output: their structure and what makes each valid.
_Avoid_: interface, spec.

**Context**: the set of tokens a model sees when it runs. Finite, with diminishing returns: every token a node loads
must earn its place.

**Agent**: the model that does a node's judgment work, run through one Hermes profile.

**Profile**: the Hermes profile an agent runs through. The human sets only its model and credentials; code applies
the rest from `ergon/hermes.yaml` before each run. `agents/AGENTS.md` has one card per profile.

**Wiki tool**: ergon's own read-only tool, which every agent has: search the wiki and read pages, and, when code
scopes the run to the project's repos, search and read code. Scoped by code per run. Build's agent also has Hermes'
terminal and file tools.

**Belt**: the folders a node's requests move through: inbox, working, waiting, review, done, rejected.
_Avoid_: queue, channel.

**Request**: one JSON file on a belt, valid against its type's contract.
_Avoid_: message, ticket.

**Proposal**: an agent's output that waits for the human's approval before code applies it.

**Story**: a user story, Plan's output: one capability a user can see or use, with observable `done_when` criteria.

**Task**: Split's output: one change the builder makes with no design decision, naming its files, the pieces to create or change with their interfaces and data shapes, and the criteria it covers.

**Round**: one planner answer: questions for the human, or the final stories.
