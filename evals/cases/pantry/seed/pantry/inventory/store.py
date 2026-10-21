"""The bakery's book, saved in pantry.json in the folder the program runs from.

Stock is kept as lots, one per delivery: {"item", "qty" (base unit), "expires" (YYYY-MM-DD)}. A lot can be used up
to and including its use-by date. Sales go in "sales": {"product", "count", "day"}.
"""
import json
from datetime import date
from pathlib import Path

from .errors import PantryError

FILE = Path("pantry.json")


def load() -> dict:
    book = json.loads(FILE.read_text()) if FILE.exists() else {}
    book.setdefault("lots", [])
    book.setdefault("sales", [])
    return book


def save(book: dict) -> None:
    FILE.write_text(json.dumps(book, indent=2) + "\n")


def today() -> str:
    return date.today().isoformat()


def fresh(lot: dict, day: str) -> bool:
    return lot["expires"] >= day


def available(book: dict, item: str, day: str | None = None) -> int:
    """The stock of an item: expired lots never count, they wait to be thrown away."""
    day = day or today()
    return sum(lot["qty"] for lot in book["lots"] if lot["item"] == item and fresh(lot, day))


def add_lot(book: dict, item: str, qty: int, expires: str) -> None:
    try:
        date.fromisoformat(expires)
    except ValueError:
        raise PantryError(f"Use-by date {expires} is not a date like 2026-12-31.") from None
    book["lots"].append({"item": item, "qty": qty, "expires": expires})


def take(book: dict, item: str, qty: int, day: str | None = None) -> None:
    """Uses the lots that expire first. Expired lots are never used; a lot used up leaves the book."""
    day = day or today()
    lots = sorted((lot for lot in book["lots"] if lot["item"] == item and fresh(lot, day)), key=lambda l: l["expires"])
    left = qty
    for lot in lots:
        used = min(lot["qty"], left)
        lot["qty"] -= used
        left -= used
        if not left:
            break
    book["lots"] = [lot for lot in book["lots"] if lot["qty"] > 0]
