# List students

A user lists every student who has a grade.

## Sub-features

- `students-list` prints one student per line, in name order.
- `students-empty` prints `No students yet.`

## How to get to it (user POV)

- Run `python3 gradebook.py students`.

## Driving it with app

Preconditions:

- A fresh state: `sh gradebook/.agents/skills/verify/app --reset s1`.

- **Empty.** Run `sh gradebook/.agents/skills/verify/app s1 students`. Output holds `No students yet.`
- **List.** Run `sh gradebook/.agents/skills/verify/app s1 add Bo hw1 80`, `sh gradebook/.agents/skills/verify/app s1 add Ana hw1 90`, then `sh gradebook/.agents/skills/verify/app s1 students`. Output holds `Ana` and `Bo`, Ana first.

## Gotchas

- A student appears once however many grades they have.
