---
name: verify
description: Drive the Ruiz Bakery's pantry command-line program the way a user does, to prove a change works. Use for every check of Ruiz Bakery's pantry's behavior.
---

# Verify Ruiz Bakery's pantry

Ruiz Bakery's pantry is a short-lived command-line program, run as `python3 pantry.py <command>`. The program is its own harness: `app` runs one
command in an isolated state folder and prints the exit code. Run everything from the project folder.

## Launch
Nothing to start or keep alive, and nothing to build. Each drive is one `app` call in a named state; `--reset`
gives a state an empty data dir. Teardown is `--reset`, or nothing.

## Doctor
`sh pantry/.agents/skills/verify/app --doctor`: Python present, the program written, `.verify/` ignored by git. Ends `exit 0` when ready to drive.

## Drive
```bash
sh pantry/.agents/skills/verify/app --reset s1
sh pantry/.agents/skills/verify/app s1 <command> [arguments]
```
A state (`s1`) is the folder `pantry/.verify/s1/`: its `pantry.json` (the bakery's book), and every file the program writes there. Commands in
the same state see each other's changes. Two states never share data, so drives in different states can run side
by side.

Quantities are typed with a unit (`25kg`, `500g`, `2l`, `30un`) and shown in each item's base unit. Use
far-future use-by dates (2099) unless the criterion is about expiry: the program compares them with today.

## Evidence
The proof is `app`'s printed output: the result line the criterion is about, and the last line, `exit <n>`
(`exit 0`, or `exit 1` when the program rejects input; its message prints just before). Standards:
- Start each criterion's proof with `--reset` on its own state, and set up data through the program's own
  commands. Do not write the program's data files by hand.
- Drive what a user types; do not import the program to call functions. Unit tests are not a proof.
- Cover the paths the change touches: the result, the error and its exit code, the empty case.
- Prove a mutation by reading it back with a second command in the same state.
- To show a file the program wrote, `cat pantry/.verify/s1/<file>`.

## Cleanup
`sh pantry/.agents/skills/verify/app --reset <state>` empties a state. Nothing runs in the background, so no process outlives a drive. Never
delete `.verify/` by hand while another drive may use it.

## Helpers
`app` (this folder): `--help`, `--doctor`, `--reset`. It needs only `sh` and `python3`.

## Feature map
`features/README.md` (below, in your prompt) lists every feature; open a feature's file for its recipe.
