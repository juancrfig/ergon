# Code

- `schema.py`: the JSON Schema subset contracts use. Extend it here before using a new keyword in a contract.
- `belt.py`: a node's request folders, atomic moves between them, and every request with its state.
- `agent.py`: runs a node agent through its Hermes profile, or through agy when `ERGON_AGENT=agy` (ADR 0029), logs
  every call, and checks its JSON answer against a contract.
- `profiles.py`: picks the backend (Hermes or agy); creates the node agents' Hermes profiles, applies
  `hermes.yaml` to them, and refuses a run while a profile is missing or has no model (ADR 0019).
- `wikitool.py`: ergon's read-only tool, scoped per run: the wiki (ADR 0016), and repos for Split (ADR 0025).
  Standalone: imports nothing from ergon.
- `wiki.py`: the project wiki and every wiki operation with one right answer.
- `node.py`: what every node shares: belt, contracts, request checks, the run loop, hand-offs, rejection; and the
  project's repos.
- `intake.py`: the Intake node.
- `plan.py`: the Plan node; also the story text and criterion ids later nodes use.
- `split.py`: the Split node.
- `build.py`: the Build node; owns the plan branches and commits.
- `proof.py`: the verification-skill check and the check of the builder's proof against its session logs (ADR 0033).
- `ticket.py`: a ticket's progress, derived from the belts on every query; nothing stored (ADR 0032).
- `cli.py`: the command line, the first adapter (ADR 0012), and `install`. A new node is added to its `NODES`.
- `hermes.yaml`: the canonical Hermes config of every node agent (ADR 0019).

Code does every step with one right answer; the model gets only judgment work (ADR 0007). The agent's prompt is
built in the node module (ADR 0008); it reads the rest through the wiki tool (ADR 0016), and Build's agent also
through the terminal (ADR 0023). A node reads another node's output only through that node's class (`Plan.approved`,
`Split.tasks`) and sends it work with `hand_off` (ADR 0026). Never let Hermes add skills, memory or project files.
