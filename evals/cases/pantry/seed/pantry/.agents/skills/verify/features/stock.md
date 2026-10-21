# Stock

A user sees every catalog item and how much is in stock.

## Sub-features

- `stock-list` prints one line per catalog item, such as `flour: 25 kg`.

## How to get to it (user POV)

- Run `python3 pantry.py stock`.

## Driving it with app

Preconditions:

- A fresh state: `sh pantry/.agents/skills/verify/app --reset s1`.

- **Empty book.** Run `sh pantry/.agents/skills/verify/app s1 stock`. Every catalog item is listed, with nothing in stock.
- **After a delivery.** Run `sh pantry/.agents/skills/verify/app s1 receive flour 25kg 2099-12-31`, then `sh pantry/.agents/skills/verify/app s1 stock`. Output holds `flour: 25 kg`.

## Gotchas

- Items with nothing in stock are still listed.
