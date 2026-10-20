"""Ruiz Bakery to-do list. Run: python3 todo.py <command> [arguments]."""
import json
import sys
from pathlib import Path

FILE = Path("todo.json")


def load() -> dict:
    return json.loads(FILE.read_text()) if FILE.exists() else {"next": 1, "items": []}


def save(data: dict) -> None:
    FILE.write_text(json.dumps(data, indent=2) + "\n")


def find(data: dict, number: str, removed: bool = False):
    return next((i for i in data["items"] if str(i["number"]) == number and i["removed"] == removed), None)


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main(args: list) -> int:
    if not args:
        return fail("usage: todo.py add|list|done|remove|restore")
    data, command, rest = load(), args[0], args[1:]
    if command == "add":
        item = {"number": data["next"], "text": " ".join(rest), "done": False, "removed": False}
        data["next"] += 1
        data["items"].append(item)
        save(data)
        print(f"Added {item['number']}: {item['text']}")
    elif command == "list":
        shown = [i for i in data["items"] if not i["removed"]]
        shown.sort(key=lambda i: (i["done"], i["number"]))
        print("\n".join(f"{i['number']}. [{'x' if i['done'] else ' '}] {i['text']}" for i in shown) or "Nothing to do.")
    elif command in ("done", "remove", "restore"):
        number = rest[0] if rest else ""
        item = find(data, number, removed=command == "restore")
        if not item:
            return fail(f"No removed item {number}." if command == "restore" else f"No item {number}.")
        if command == "done":
            item["done"] = True
        else:
            item["removed"] = command == "remove"
        save(data)
        word = {"done": "Done", "remove": "Removed", "restore": "Restored"}[command]
        print(f"{word} {item['number']}: {item['text']}")
    else:
        return fail(f"unknown command {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
