# Recipes

A user sees what one batch of a product takes.

## Sub-features

- `recipe-show` prints one line per ingredient.
- `recipe-unknown` refuses an unknown recipe.

## How to get to it (user POV)

- Run `python3 pantry.py recipe <name>`.

## Driving it with app

Preconditions:

- A fresh state: `sh pantry/.agents/skills/verify/app --reset s1`.

- **Show.** Run `sh pantry/.agents/skills/verify/app s1 recipe croissant`. Output lists its ingredients and ends `exit 0`.
- **Unknown.** Run `sh pantry/.agents/skills/verify/app s1 recipe pizza`. Output ends `exit 1`.

## Gotchas

- Recipes are fixed in the program; no command adds one.
