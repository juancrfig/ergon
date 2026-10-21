---
name: verify
description: Drive Ruiz Bakery's pantry command-line program to prove a change works. Use for every check of pantry's behavior.
---

# Verify pantry

pantry is a command-line program, so the program is the interface: `app` only runs it in a state folder and prints
its exit code. Run it from the project folder:

```bash
sh pantry/.agents/skills/verify/app --reset s1
sh pantry/.agents/skills/verify/app s1 receive flour 25kg 2099-12-31
sh pantry/.agents/skills/verify/app s1 stock
```

- A state (`s1`) is a folder under `pantry/.verify/` holding that state's `pantry.json` (the bakery's book); git
  ignores it. A new state starts with an empty book. Commands in the same state see each other's changes.
- The last line is the exit code: `exit 0`, or `exit 1` for a user mistake, whose message prints on the line
  before it.
- Nothing runs in the background, so there is nothing to start or stop. `--help` lists the options;
  `app s1 help` lists pantry's commands.

## Proof bar
- Start each criterion's proof with `--reset` on its own state, then set up the book through pantry's own commands
  (`receive`, `sell`). Do not write `pantry.json` by hand.
- Drive the commands a user types; do not import the modules to call functions. The unit tests in `tests/` check
  modules, not the program; they are not a proof.
- Use far-future use-by dates (2099) unless the criterion is about expiry: the program compares them with today.
- Cover the paths the change touches: the result, the error and its exit code, the empty book, and that a change
  persists (read it back with a second command in the same state).

## Feature map
FEATURES.md, next to this file.
