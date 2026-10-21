"""What the shop sold: products and counts per day. Used for the end-of-day summary."""
from . import recipes, store


def record(book: dict, product: str, count: int) -> None:
    recipes.get(product)
    book["sales"].append({"product": product, "count": count, "day": store.today()})


def day_totals(book: dict, day: str) -> dict:
    """Product -> count sold that day, in the order first sold."""
    totals: dict = {}
    for sale in book["sales"]:
        if sale["day"] == day:
            totals[sale["product"]] = totals.get(sale["product"], 0) + sale["count"]
    return totals


def flour_sold(book: dict, day: str) -> int:
    """Grams of flour in what sold that day, at 20 pieces a batch: the owner's rough check of the day."""
    return sum(recipes.get(p)["flour"] * count // 20 for p, count in day_totals(book, day).items())
