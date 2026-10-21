"""The command line. Every command loads the book, does one thing, saves if it changed something and prints one
line per result. Errors are PantryError: printed to stderr, exit code 1."""
import sys

from . import catalog, labels, recipes, sales, store, units
from .errors import PantryError

HELP = """Commands:
  stock                           every item and how much is in stock
  receive <item> <qty> <use-by>   a delivery: python3 pantry.py receive flour 25kg 2026-12-31
  use <item> <qty>                take stock out, the lot that expires first first
  recipe <name>                   what one batch takes
  sell <product> <count>          record a sale
  sales                           today's sales
  label <item>                    shelf label lines for an item"""


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except PantryError as error:
        print(error, file=sys.stderr)
        return 1


def run(argv: list[str]) -> int:
    command, args = (argv[0], argv[1:]) if argv else ("help", [])
    book = store.load()
    if command == "stock":
        for item in catalog.ITEMS:
            print(f"{item.name}: {units.show(store.available(book, item.name), item.base)}")
    elif command == "receive" and len(args) == 3:
        item = catalog.get(args[0])
        qty = units.parse(args[1], item.base)
        store.add_lot(book, item.name, qty, args[2])
        store.save(book)
        print(f"Received {units.show(qty, item.base)} of {item.name}")
    elif command == "use" and len(args) == 2:
        item = catalog.get(args[0])
        qty = units.parse(args[1], item.base)
        have = store.available(book, item.name)
        if qty > have:
            raise PantryError(f"Not enough {item.name}: {units.show(have, item.base)} in stock.")
        store.take(book, item.name, qty)
        store.save(book)
        print(f"Used {units.show(qty, item.base)} of {item.name}")
    elif command == "recipe" and len(args) == 1:
        for name, qty in recipes.get(args[0]).items():
            print(f"{name}: {units.show(qty, catalog.get(name).base)}")
    elif command == "sell" and len(args) == 2:
        count = whole(args[1], "Count")
        sales.record(book, args[0], count)
        store.save(book)
        print(f"Sold {count} {args[0]}")
    elif command == "sales" and not args:
        totals = sales.day_totals(book, store.today())
        for product, count in totals.items():
            print(f"{product}: {count}")
        if not totals:
            print("No sales today.")
    elif command == "label" and len(args) == 1:
        found = labels.lines(book, args[0])
        print("\n".join(found) if found else f"No {args[0]} in stock.")
    else:
        print(HELP)
        return 0 if command == "help" else 1
    return 0


def whole(text: str, what: str) -> int:
    """A count typed by the user: a whole number above 0."""
    if not text.isdigit() or int(text) == 0:
        raise PantryError(f"{what} must be a whole number above 0.")
    return int(text)
