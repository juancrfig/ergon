# splitbill verification map

The maintained source for verifying what splitbill does for a user. Read this index, then use the matching feature
file as the recipe.

## Baseline preconditions
- `sh splitbill/.agents/skills/verify/app --doctor` ends `exit 0`.
- Each recipe runs in a fresh state: `sh splitbill/.agents/skills/verify/app --reset <state>`.

## Driving conventions
- Every action is one `app` call: `sh splitbill/.agents/skills/verify/app <state> <command> ...`. Treat commands as literal.
- Set up data through the program's commands, never by writing its files.

## Proof and skip reporting
- Proof is the printed result line plus the final `exit <n>` line.
- A mutation's proof includes a second command in the same state that reads it back.
- Do not report an entry point as verified through a different one.

## Feature entry contract
Each feature file starts with an H1 title and one paragraph of user-visible behavior, then four H2s in this
order: `Sub-features`, `How to get to it (user POV)`, `Driving it with app` (starting with `Preconditions:`), and
`Gotchas`. No implementation details: user paths, commands, required state and observable proof only.

## Features

None yet: splitbill is not written. The builder that adds a feature adds its file here and a line to this list.
