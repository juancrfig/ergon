# Report averages

A user sees each student's average over all their grades, one line per student in name order.

## Sub-features

- `report-averages` prints `<student>: <average>` with one decimal.
- `report-rounding` rounds halves up (82.25 shows 82.3).
- `report-empty` prints `No grades yet.` for an empty book.

## How to get to it (user POV)

- Run `python3 gradebook.py report`.

## Driving it with app

Preconditions:

- A fresh state: `sh gradebook/.agents/skills/verify/app --reset s1`.

- **Empty.** Run `sh gradebook/.agents/skills/verify/app s1 report`. Output holds `No grades yet.` and `exit 0`.
- **Averages.** Run `sh gradebook/.agents/skills/verify/app s1 add Ana hw1 90`, `sh gradebook/.agents/skills/verify/app s1 add Ana hw2 95`, then `sh gradebook/.agents/skills/verify/app s1 report`. Output holds `Ana: 92.5`.

## Gotchas

- Order is by name, not by when a student was added.
