# Shelf labels

A user prints label lines for each lot of an item in stock.

## Sub-features

- `label-lots` prints one label line per lot.
- `label-none` prints `No <item> in stock.`

## How to get to it (user POV)

- Run `python3 pantry.py label <item>`.

## Driving it with app

Preconditions:

- A fresh state: `sh pantry/.agents/skills/verify/app --reset s1`.

- **None.** Run `sh pantry/.agents/skills/verify/app s1 label flour`. Output holds `No flour in stock.`
- **Lots.** Run `sh pantry/.agents/skills/verify/app s1 receive flour 25kg 2099-12-31`, then `sh pantry/.agents/skills/verify/app s1 label flour`. Output holds a line with `2099-12-31`.

## Gotchas

- One line per lot, not per item.
