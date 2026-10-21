# Sales

A user records sales of a product and sees today's totals per product.

## Sub-features

- `sell` records a sale and prints `Sold <count> <product>`.
- `sales-today` prints `<product>: <count>` lines.
- `sales-empty` prints `No sales today.`
- `sell-reject` refuses a count that is not a whole number above 0.

## How to get to it (user POV)

- Run `python3 pantry.py sell <product> <count>`.
- Run `python3 pantry.py sales`.

## Driving it with app

Preconditions:

- A fresh state: `sh pantry/.agents/skills/verify/app --reset s1`.

- **Empty.** Run `sh pantry/.agents/skills/verify/app s1 sales`. Output holds `No sales today.`
- **Sell.** Run `sh pantry/.agents/skills/verify/app s1 sell croissant 12`. Output holds `Sold 12 croissant` and `exit 0`.
- **Totals.** Run `sh pantry/.agents/skills/verify/app s1 sales`. Output holds `croissant: 12`.
- **Reject.** Run `sh pantry/.agents/skills/verify/app s1 sell croissant 0`. Output holds `Count must be a whole number above 0.` and `exit 1`.

## Gotchas

- Totals are for today only; sales from other days do not show.
