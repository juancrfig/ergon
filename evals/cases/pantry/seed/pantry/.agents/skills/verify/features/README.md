# pantry verification map

The maintained source for verifying what pantry does for a user. Read this index, then use the matching feature
file as the recipe.

## Baseline preconditions
- `sh pantry/.agents/skills/verify/app --doctor` ends `exit 0`.
- Each recipe runs in a fresh state: `sh pantry/.agents/skills/verify/app --reset <state>`.

## Driving conventions
- Every action is one `app` call: `sh pantry/.agents/skills/verify/app <state> <command> ...`. Treat commands as literal.
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

- [Stock](./stock.md) covers the stock list.
- [Receive a delivery](./receive.md) covers adding lots and rejected deliveries.
- [Use stock](./use.md) covers taking stock out, first-expiring lot first, and shortages.
- [Recipes](./recipes.md) covers showing a recipe and unknown recipes.
- [Sales](./sales.md) covers recording sales, today's totals and rejected counts.
- [Shelf labels](./labels.md) covers label lines per lot and items with no stock.

`help` lists the commands and exits 0; an unknown command prints the same list and exits 1.
