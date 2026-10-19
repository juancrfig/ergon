# Code

- `schema.py`: the JSON Schema subset contracts use. Extend it here before using a new keyword in a contract.
- `belt.py`: a node's request folders and atomic moves between them.
- `agent.py`: runs a node agent through its Hermes profile and checks its JSON answer against a contract.
- `gate.py`: refuses a run when the agent's Hermes profile does not exist.
- `wiki.py`: the project wiki and every wiki operation with one right answer.
- `intake.py`: the Intake node.
- `cli.py`: the command line.

Code does every step with one right answer; the model gets only judgment work (ADR 0007). The agent's entire
context is built in the node module (ADR 0008): never let Hermes add skills, memory or project files.
