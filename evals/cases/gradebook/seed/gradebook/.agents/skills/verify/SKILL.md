---
name: verify
description: Drive the gradebook command-line program to prove a change works. Use for every check of gradebook's behavior.
---

# Verify gradebook

gradebook is a command-line program, so the program is the interface: `app` only runs it in a state folder and
prints its exit code. Run it from the project folder:

```bash
sh gradebook/.agents/skills/verify/app --reset s1
sh gradebook/.agents/skills/verify/app s1 add Ana hw1 90
sh gradebook/.agents/skills/verify/app s1 report
```

- A state (`s1`) is a folder under `gradebook/.verify/` holding that state's `grades.json` and any file the program
  writes; git ignores it. A new state starts with no grades. Commands in the same state see each other's changes.
- The last line is the exit code: `exit 0`, or `exit 1` when the program rejects the input. Errors print on the
  line before it.
- Nothing runs in the background, so there is nothing to start or stop. `--help` lists the options.

## Proof bar
- Start each criterion's proof with `--reset` on its own state, then set up the data through the program's own
  commands. Do not write `grades.json` by hand.
- Drive the commands a user types; do not import the module to call functions.
- Cover the paths the change touches: the result, the error and its exit code, the empty book, and that a change
  persists (read it back with a second command in the same state).
- To read a file the program writes, `cat` it inside the state folder: `cat gradebook/.verify/s1/<file>`.

## Feature map
FEATURES.md, next to this file.
