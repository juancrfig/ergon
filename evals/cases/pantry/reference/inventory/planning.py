"""Planned bakes: recipes and batches the bakery will make. They are kept in the book until baked."""
from . import catalog, recipes, store


def planned_needs(book: dict) -> dict:
    """Item -> quantity every planned bake together takes."""
    total: dict = {}
    for bake in book.get("planned", []):
        for item, qty in recipes.needs(bake["recipe"], bake["batches"]).items():
            total[item] = total.get(item, 0) + qty
    return total


def plan(book: dict, recipe: str, batches: int) -> list:
    """Records the bake and returns (item, short) for each item it lacks, in catalog order. Stock already taken by
    earlier planned bakes is not there for this one."""
    earlier = planned_needs(book)
    needs = recipes.needs(recipe, batches)
    book.setdefault("planned", []).append({"recipe": recipe, "batches": batches})
    out = []
    for item in catalog.ITEMS:
        if item.name in needs:
            short = needs[item.name] - (store.available(book, item.name) - earlier.get(item.name, 0))
            if short > 0:
                out.append((item, min(short, needs[item.name])))
    return out
