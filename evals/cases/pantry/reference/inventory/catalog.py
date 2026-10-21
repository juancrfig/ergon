"""What the bakery stocks. Every item has a base unit, a minimum, a target and the supplier it comes from."""
from dataclasses import dataclass

from .errors import PantryError


@dataclass(frozen=True)
class Item:
    name: str
    base: str        # g, ml or un: see units.py
    minimum: int     # below this, the item needs an order
    target: int      # an order brings the stock back up to this
    supplier: str    # a key of suppliers.SUPPLIERS


# In the order the bakery wants every list printed.
ITEMS = [
    Item("flour", "g", 20000, 75000, "molinos"),
    Item("sugar", "g", 5000, 15000, "dulce"),
    Item("butter", "g", 4000, 10000, "lacteos"),
    Item("milk", "ml", 10000, 24000, "lacteos"),
    Item("eggs", "un", 60, 180, "granja"),
    Item("yeast", "g", 500, 1000, "dulce"),
]


def get(name: str) -> Item:
    for item in ITEMS:
        if item.name == name:
            return item
    raise PantryError(f"Unknown item {name}. Items: {', '.join(i.name for i in ITEMS)}.")


def shortfall(item: Item, stock: int) -> int:
    """How much an order should bring in: nothing while the stock is at or above the minimum; once it is below,
    enough to reach the target (not the minimum)."""
    return item.target - stock if stock < item.minimum else 0
