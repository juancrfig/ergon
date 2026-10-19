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
the rest from `profiles/hermes.yaml` before each run. `profiles/AGENTS.md` has one card per profile.

**Wiki tool**: the agents' only tools: search the wiki and read pages. Read-only, scoped by code to one wiki per
run.

**Belt**: the folders a node's requests move through: inbox, working, waiting, review, done, rejected.
_Avoid_: queue, channel.

**Request**: one JSON file on a belt, valid against its type's contract.
_Avoid_: message, ticket.

**Proposal**: an agent's output that waits for the human's approval before code applies it.

**Story**: a user story, Plan's output: one capability a user can see or use, with observable `done_when` criteria.

**Round**: one planner answer: questions for the human, or the final stories.
