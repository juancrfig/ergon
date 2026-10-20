"""Grade book for one class. Run: python3 gradebook.py <command> [arguments].

Grades live in grades.json, in the folder the program runs from.
"""
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

FILE = Path("grades.json")


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


def cmd_add(args: list, book: dict) -> None:
    if len(args) != 3:
        raise GradebookError("usage: gradebook.py add <student> <assignment> <score>")
    student, assignment, score = args[0], args[1], parse_score(args[2])
    for grade in book["grades"]:
        if grade["student"] == student and grade["assignment"] == assignment:
            grade["score"] = score
            save(book)
            say(f"Updated {score} for {student} on {assignment}")
            return
    book["grades"].append({"student": student, "assignment": assignment, "score": score})
    save(book)
    say(f"Added {score} for {student} on {assignment}")


def cmd_report(args: list, book: dict) -> None:
    names = students(book)
    if not names:
        say("No grades yet.")
    for name in names:
        scores = [g["score"] for g in book["grades"] if g["student"] == name]
        say(f"{name}: {one_decimal(average(scores))}")


def cmd_students(args: list, book: dict) -> None:
    say("\n".join(students(book)) or "No students yet.")


COMMANDS = {"add": cmd_add, "report": cmd_report, "students": cmd_students}


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
