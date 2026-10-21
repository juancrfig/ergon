# 0030. Build gets the text of the files it works on

Status: accepted, 2026-10-21

## Context
The builder's prompt held the skill, the story, the criteria, the task and the answer contract, about 6,700
characters, and no code. In the 35 builder calls of the first agy rounds, it spent about 21 model turns per task,
mostly finding its way: about 280 directory listings, file searches and file views, and 171 git commands, against 64
edits. Each turn resends the whole conversation, so a task cost about 480,000 tokens. Split already reads the code and
names the files each task changes, but not the files the builder must read for the edit to fit (a helper it calls, a
module it imports, a test it must keep passing).

## Decision
- Each task gains `read`: every other existing file the builder needs. The architect names it; code checks that each
  one is in a project repo, exists (or an earlier task creates it) and is not already in `files`.
- Build puts the current text of every file the task changes or deletes, and of every `read` file, in the builder's
  prompt, read from the plan branch when the task starts, so it includes earlier tasks' commits. Whole files, no cap:
  a prompt too big for the model fails the run loudly.
- The builder may still open other files; the skill says to start from the given ones.
- A file the builder had to find by itself is a gap of Split, visible in its tool calls.

## Consequences
- Fewer turns spent finding files, if the architect names them well; the next eval round measures it against the
  rounds of 2026-10-20 (turns and tokens per builder call).
- Split outputs from before this ADR have no `read`; Build treats it as empty, so old snapshots still run.
- Not addressed here: the git commands the builder runs to see the repo state, and the builder reading outside the
  project folder.

## Result
First round after this ADR and the prompt cleanup that came with it (gradebook × 3 on agy/Gemini 3.8 Flash,
2026-10-21): 3/3 trials passed, 9/9 builder calls accepted; per builder call 15.1 turns and about 357,000 tokens,
against 20.5 turns and about 608,000 tokens in the two gradebook trials of 2026-10-20. Split named no `read` file
(gradebook has one code file), so this measures the given changed-file text, not `read`; several prompt changes
shipped together, so no single one owns the drop.
