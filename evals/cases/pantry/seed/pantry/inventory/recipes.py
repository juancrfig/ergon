"""What one batch of each product takes, per item, in the item's base unit."""
from .errors import PantryError

RECIPES = {
    "baguette": {"flour": 5000, "yeast": 100},
    "croissant": {"flour": 2000, "butter": 1500, "milk": 500, "sugar": 200, "eggs": 4, "yeast": 50},
    "pan-de-leche": {"flour": 3000, "milk": 1500, "sugar": 400, "butter": 300, "eggs": 6, "yeast": 60},
}


def get(name: str) -> dict:
    if name not in RECIPES:
        raise PantryError(f"Unknown recipe {name}. Recipes: {', '.join(RECIPES)}.")
    return RECIPES[name]


def needs(name: str, batches: int) -> dict:
    """Item -> quantity for that many batches, in the recipe's order."""
    return {item: qty * batches for item, qty in get(name).items()}
