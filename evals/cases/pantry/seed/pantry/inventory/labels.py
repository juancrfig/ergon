"""Shelf labels: one line per lot of an item still in use, the one to use first on top."""
from . import catalog, store, units


def lines(book: dict, name: str) -> list[str]:
    item = catalog.get(name)
    day = store.today()
    lots = sorted((l for l in book["lots"] if l["item"] == name and store.fresh(l, day)), key=lambda l: l["expires"])
    return [f"{name.upper()} | {units.show(l['qty'], item.base)} | use by {l['expires']}" for l in lots]
