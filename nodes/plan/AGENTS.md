# Plan node

Turns a goal into user stories. Agent: `planner` (agents/AGENTS.md), frontier-reasoning. Decisions: ADR 0011, 0013,
0015-0017, 0019, 0028, 0032.

## Input
- `plan`: the human's goal and the ticket it delivers (ADR 0032). `contracts/request.plan.json`. Documents go
  through Intake first.
- Answers to a round of questions. `contracts/answers.json`

## Output
- Each round (`contracts/round.json`): questions, which wait in `waiting/` for answers, or stories, which wait in
  `review/` for approval. At most 5 rounds.
- Approved stories: `runs/<id>/stories.json`. Each `done_when` criterion's id is `<story id>#<n>`, its 1-based
  position; approved stories never change, so later nodes cite criteria by it. Approving puts a split request on
  Split's belt (ADR 0024).
- The answered rounds, when stories come back after at least one: a source in `wiki/raw/` and an ingest request on
  Intake's belt. Approving the plan applies that wiki change first; rejecting the plan rejects it (ADR 0028).

## Who does what
- Code: request and answer checks, the planner's prompt (goal, wiki index, earlier rounds) and tool scope, round
  checks (unique ids, recommendation among the options, sources are real pages), skipped answers
  take the recommendation.
- Agent: reads the wiki pages it needs through the wiki tool (ADR 0016), and the project's code, read-only, to check what the goal assumes exists (ADR 0035); asks the questions that change the
  stories; writes the stories.
- Human: answers, then approves or rejects the stories.

## Commands
```
python3 -m ergon install              # once: profiles and folders (repo root, --project <project>)
hermes -p planner model          # once: set its model and credentials by hand
python3 -m ergon submit goal.json            # {"type": "plan", "from": "juanes", "ticket": "ABC-123", "goal": "..."}
python3 -m ergon run plan                    # one round per plan in the inbox
python3 -m ergon pending
python3 -m ergon ticket [<ticket>]           # a ticket's plans and tasks; without an id, every ticket
python3 -m ergon show <id>
python3 -m ergon answer <id> answers.json    # {"answers": [{"question": "q1", "answer": "..."}]}
python3 -m ergon approve <id>   |   python3 -m ergon reject <id> "reason"
```

The belt as a diagram, for humans: `diagrams.md`. Update it when a state or a move changes. This file is the
only text description of the node.
