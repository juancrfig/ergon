---
name: verify
description: Drive the todo command-line program to prove a change works. Use for every check of todo's behavior.
---

# Verify todo

todo is a command-line program, run as `python3 todo.py <command>`, so the program is the interface: `app` only runs it in a state
folder and prints its exit code. Run it from the project folder:

```bash
sh todo/.agents/skills/verify/app --reset s1
sh todo/.agents/skills/verify/app s1 list
```

- A state (`s1`) is a folder under `todo/.verify/` holding every file the program reads or writes there; git
  ignores it. `--reset` empties it. Commands in the same state see each other's changes.
- The last line is the exit code: `exit 0`, or another code when the program rejects the input. Errors print on the
  line before it.
- Until `todo.py` exists, `app` prints Python's "can't open file" error and `exit 2`.
- Nothing runs in the background, so there is nothing to start or stop. `--help` lists the options.

## Proof bar
- Start each criterion's proof with `--reset` on its own state, then set up data through the program's own
  commands. Do not write the program's data files by hand.
- Drive the program as a user types it; do not import it to call functions.
- Cover the paths the change touches: the result, the error and its exit code, the empty case, and that a change
  persists (read it back with a second command in the same state).

## Feature map
FEATURES.md, next to this file. Add each feature you build to it, in the same task.
