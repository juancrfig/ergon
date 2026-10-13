# Spec approval template

`approval.md` sits next to `spec.md`. The human reads and approves only this file; `spec.md` stays the full document
for agents. Keep it to about one phone screen. If it does not fit, the ticket is too big: split it.

## Who writes what

- Scenarios: a subagent that did not write the spec. It reads `spec.md` and writes one scenario per behaviour the user
  can observe. Where the spec forces it to guess, it writes an Open question instead of a scenario.
- Decisions, Not doing, Open: the main agent.

## Rules

- **Scenarios** are what layer 2 (evidence runs) proves, and later what approved tests cover. Two kinds, proved the
  same way:
  - **Key** (at most 10): the ones the human must read: core behaviour, user-visible risk, anything 🔒. Written in
    full. If more than 10 are key, the ticket is too big: split it.
  - **More** (no limit): further edge cases and regressions. One line each: id and title only, so the human can ask
    to expand any of them. Their full Given/When/Then lives in `spec.md` under "Scenarios".
- Each key scenario has an id (`S1`), a short title and three lines:
  Given (a real starting state), When (one user action or event), Then (something observable on the screen or in a
  named data source, never "works correctly"). Use real data where possible.
- Mark a scenario 🔒 when proving it needs something the human must allow (a test sheet, real alerts, another
  system). Say what, in a few words.
- **Decisions**: only those the human could not guess from their known preferences, or with a large blast radius.
  One line each: the decision, why, and the rejected alternative. Mark ⚠️ when it is costly to reverse or the user
  will feel it.
- **Not doing**: one line each, only what someone could reasonably expect.
- **Open**: questions the human must answer before approval. Omit the section when empty.
- No problem statement, no background, no file names, no code. Same language as the conversation with the human.

## Template

```markdown
# <Ticket title>

**Outcome:** <one sentence: what users can see or do after this ships>

## Scenarios

**S1 · <title>**
Given <starting state>
When <action or event>
Then <observable result>

**More:** S11 · <title> · S12 · <title>

## Decisions

- <decision>: <why>. Not <rejected alternative>: <why not>.

## Not doing

- <item>

## Open

- <question>
```
