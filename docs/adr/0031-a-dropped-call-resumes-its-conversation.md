# 0031. A dropped call resumes its conversation

Status: accepted, 2026-10-21

## Context
A call the connection dropped ran again from the start (ADR 0029). In the pantry round of 2026-10-21, Google's
service went silent for 5 minutes in the middle of a Build task; agy stopped the call, and the retry redid the whole
task: 648 seconds of work thrown away, 288 more to redo it. Hermes had no retry at all: a provider outage after its
own retries failed the node.

## Decision
A call that fails on a connection error resumes its own conversation once, as `<label>-resume`, with a short prompt:
continue the same task from where you stopped, and end with the answer the task asks for. The model keeps every step
and tool result from before the drop.

- **Hermes**: `hermes chat --resume <session>`, when the call exits with Hermes' "temporarily unavailable" message
  and printed a session id.
- **agy**: `agy --conversation <id>` in the same throwaway HOME, kept until the resumed call ends. When agy failed
  before it started a conversation, the call still runs once more as `<label>-retry`.
- Both backends report the whole conversation's tokens after a resume, so the resumed call's record subtracts the
  dropped call's: `calls.jsonl` counts every token once.

## Consequences
- A drop costs the time of the drop, not the work before it.
- **A new backend must implement this too.** Without it, a dropped call starts over (agy's `-retry`) or fails the
  node (Hermes before this ADR). Out of scope until a third backend is added.
- Checked by forcing a drop on a real call of each backend: the resumed call answered from the first call's context.
