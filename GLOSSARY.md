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

**Profile**: an agent's definition in the ergon repo: its Hermes config and its skills. The installed copy must match
it (the context gate).

**Belt**: the folders a node's requests move through: inbox, working, review, done, rejected.
_Avoid_: queue, channel.

**Request**: one JSON file on a belt, valid against its type's contract.
_Avoid_: message, ticket.

**Proposal**: an agent's output that waits for the human's approval before code applies it.
