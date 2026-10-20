"""Grade book for one class. Run: python3 gradebook.py <command> [arguments].

Grades live in grades.json, in the folder the program runs from.
"""
import csv
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

FILE = Path("grades.json")
WEIGHTS = {"homework": 40, "exam": 60}   # the school's rule; a grade with no category is homework


class GradebookError(Exception):
    """A mistake in what the user typed: main prints it as an error and exits with code 1."""


def load() -> dict:
    return json.loads(FILE.read_text()) if FILE.exists() else {"grades": []}


def save(book: dict) -> None:
    FILE.write_text(json.dumps(book, indent=2) + "\n")


def say(text: str) -> None:
    print(text)


def one_decimal(value: Decimal) -> str:
    """Every number the program shows: one decimal, halves round up (82.25 -> 82.3)."""
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def average(scores: list) -> Decimal:
    return Decimal(sum(scores)) / len(scores)


def parse_score(text: str) -> int:
    if not text.isdigit() or int(text) > 100:
        raise GradebookError("Score must be a whole number from 0 to 100.")
    return int(text)


def students(book: dict) -> list:
    return sorted({g["student"] for g in book["grades"]})


def final(book: dict, name: str) -> tuple:
    """A student's average per category (None when the student has none) and the final grade, weighted between the
    categories the student has."""
    averages = {}
    for category in WEIGHTS:
        scores = [g["score"] for g in book["grades"]
                  if g["student"] == name and g.get("category", "homework") == category]
        averages[category] = average(scores) if scores else None
    present = {c: a for c, a in averages.items() if a is not None}
    return averages, sum(a * WEIGHTS[c] for c, a in present.items()) / sum(WEIGHTS[c] for c in present)


def cmd_add(args: list, book: dict) -> None:
    category = "homework"
    if len(args) == 5 and args[3] == "--category":
        category = args.pop(4)
        args.pop(3)
        if category not in WEIGHTS:
            raise GradebookError("Category must be homework or exam.")
    if len(args) != 3:
        raise GradebookError("usage: gradebook.py add <student> <assignment> <score> [--category homework|exam]")
    student, assignment, score = args[0], args[1], parse_score(args[2])
    for grade in book["grades"]:
        if grade["student"] == student and grade["assignment"] == assignment:
            grade.update(score=score, category=category)
            save(book)
            say(f"Updated {score} for {student} on {assignment}")
            return
    book["grades"].append({"student": student, "assignment": assignment, "score": score, "category": category})
    save(book)
    say(f"Added {score} for {student} on {assignment}")


def cmd_report(args: list, book: dict) -> None:
    names = students(book)
    if not names:
        say("No grades yet.")
    for name in names:
        say(f"{name}: {one_decimal(final(book, name)[1])}")


def cmd_students(args: list, book: dict) -> None:
    say("\n".join(students(book)) or "No students yet.")


def cmd_export(args: list, book: dict) -> None:
    if len(args) != 1:
        raise GradebookError("usage: gradebook.py export <file>")
    names = students(book)
    with open(args[0], "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["student", *WEIGHTS, "final"])
        for name in names:
            averages, grade = final(book, name)
            writer.writerow([name, *(one_decimal(a) if a is not None else "" for a in averages.values()),
                             one_decimal(grade)])
    say(f"Exported {len(names)} students to {args[0]}")


COMMANDS = {"add": cmd_add, "report": cmd_report, "students": cmd_students, "export": cmd_export}


def main(argv: list) -> int:
    if not argv or argv[0] not in COMMANDS:
        print("usage: gradebook.py " + "|".join(COMMANDS) + " ...", file=sys.stderr)
        return 1
    try:
        COMMANDS[argv[0]](argv[1:], load())
    except GradebookError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
