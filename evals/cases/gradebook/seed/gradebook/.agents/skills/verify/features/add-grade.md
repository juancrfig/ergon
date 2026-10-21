# Add or update a grade

A user records a student's score on an assignment; recording the same student and assignment again replaces the score.

## Sub-features

- `add-new` records a score and prints `Added <score> for <student> on <assignment>`.
- `add-update` replaces an existing score and prints `Updated ...`.
- `add-reject` refuses a score outside 0-100 or not a whole number.

## How to get to it (user POV)

- Run `python3 gradebook.py add <student> <assignment> <score>`.

## Driving it with app

Preconditions:

- A fresh state: `sh gradebook/.agents/skills/verify/app --reset s1`.

- **Add.** Run `sh gradebook/.agents/skills/verify/app s1 add Ana hw1 90`. Output holds `Added 90 for Ana on hw1` and `exit 0`.
- **Update.** Run `sh gradebook/.agents/skills/verify/app s1 add Ana hw1 95`. Output holds `Updated` and `exit 0`.
- **Persistence.** Run `sh gradebook/.agents/skills/verify/app s1 report`. Output holds `Ana: 95.0`.
- **Reject.** Run `sh gradebook/.agents/skills/verify/app s1 add Ana hw2 101`. Output holds `Score must be a whole number from 0 to 100.` and `exit 1`.

## Gotchas

- A wrong number of arguments prints the usage and exits 1, not the score error.
- A rejected score changes nothing; prove it with `report`.
