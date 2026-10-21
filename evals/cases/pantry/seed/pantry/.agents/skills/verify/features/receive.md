# Receive a delivery

A user records a delivery: an amount of an item with a use-by date, kept as its own lot.

## Sub-features

- `receive-lot` adds a lot and prints `Received <qty> of <item>`.
- `receive-reject` refuses an item not in the catalog or a quantity in the wrong unit.

## How to get to it (user POV)

- Run `python3 pantry.py receive <item> <qty> <use-by>`, the date as YYYY-MM-DD.

## Driving it with app

Preconditions:

- A fresh state: `sh pantry/.agents/skills/verify/app --reset s1`.

- **Receive.** Run `sh pantry/.agents/skills/verify/app s1 receive flour 25kg 2099-12-31`. Output holds `Received` and `exit 0`.
- **Persistence.** Run `sh pantry/.agents/skills/verify/app s1 stock`. Output holds `flour: 25 kg`.
- **Reject.** Run `sh pantry/.agents/skills/verify/app s1 receive unobtainium 1kg 2099-12-31`. Output ends `exit 1`.

## Gotchas

- A wrong unit for the item (litres of flour) is an error, not a conversion.
