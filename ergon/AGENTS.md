# Code

- `schema.py`: the JSON Schema subset contracts use. Extend it here before using a new keyword in a contract.
- `belt.py`: a node's request folders and atomic moves between them.
- `agent.py`: runs a node agent through its Hermes profile and checks its JSON answer against a contract.
- `gate.py`: refuses a run when the agent's Hermes profile does not exist or does not start the wiki tool.
- `wikitool.py`: the agents' only tools, read-only, scoped per run (ADR 0016). Standalone: imports nothing from ergon.
- `wiki.py`: the project wiki and every wiki operation with one right answer.
- `node.py`: what every node shares: belt, contracts, request checks, replies, rejection.
- `intake.py`: the Intake node.
- `plan.py`: the Plan node.
- `cli.py`: the command line, the first adapter (ADR 0012). A new node is added to its `NODES`.

Code does every step with one right answer; the model gets only judgment work (ADR 0007). The agent's prompt is
built in the node module (ADR 0008); it reads the rest only through the wiki tool (ADR 0016). Never let Hermes add
skills, memory or project files.
