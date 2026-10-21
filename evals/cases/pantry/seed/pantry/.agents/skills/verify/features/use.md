# Use stock

A user takes stock out; it comes from the lot that expires first.

## Sub-features

- `use-fefo` takes from the first-expiring lot and prints `Used <qty> of <item>`.
- `use-short` refuses more than is in stock and takes nothing.

## How to get to it (user POV)

- Run `python3 pantry.py use <item> <qty>`.

## Driving it with app

Preconditions:

- A fresh state: `sh pantry/.agents/skills/verify/app --reset s1`.
- Two flour lots: `sh pantry/.agents/skills/verify/app s1 receive flour 25kg 2099-01-31` and `sh pantry/.agents/skills/verify/app s1 receive flour 25kg 2099-12-31`.

- **Use.** Run `sh pantry/.agents/skills/verify/app s1 use flour 30kg`. Output holds `Used` and `exit 0`.
- **Which lot.** Run `sh pantry/.agents/skills/verify/app s1 label flour`. Only the 2099-12-31 lot remains, with 20 kg.
- **Shortage.** Run `sh pantry/.agents/skills/verify/app s1 use flour 100kg`. Output holds `Not enough flour:` and `exit 1`; `stock` is unchanged.

## Gotchas

- A refused use takes nothing; prove it with `stock`.
