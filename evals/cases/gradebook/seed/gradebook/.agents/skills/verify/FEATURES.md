# gradebook feature map

What gradebook does and how a user reaches it. Every feature is a command: `python3 gradebook.py <command>`.
Drive each with `sh gradebook/.agents/skills/verify/app <state> <command> ...` (SKILL.md).

## Add or update a grade
- **What it does:** records a student's score on an assignment; the same student and assignment again replaces the
  score. Prints `Added <score> for <student> on <assignment>` or `Updated ...`.
- **How to reach it:** `add <student> <assignment> <score>`.
- **Driving it:** `app s1 add Ana hw1 90`, then `app s1 add Ana hw1 95` for an update.
- **Gotchas:** a score must be a whole number from 0 to 100; anything else prints
  `Score must be a whole number from 0 to 100.` with exit 1. A wrong number of arguments prints the usage, exit 1.

## Report averages
- **What it does:** each student's average over all their grades, one line per student in name order, one
  decimal, halves rounded up (82.25 shows 82.3).
- **How to reach it:** `report`.
- **Driving it:** add grades, then `app s1 report`, expecting lines like `Ana: 92.5`.
- **Gotchas:** an empty book prints `No grades yet.`

## List students
- **What it does:** every student with a grade, one per line, in name order.
- **How to reach it:** `students`.
- **Driving it:** `app s1 students`.
- **Gotchas:** an empty book prints `No students yet.`

## Usage
- An unknown or missing command prints `usage: gradebook.py add|report|students ...` on stderr, exit 1.
