"""The order list: what to buy, from whom, in whole packs."""
from . import catalog, planning, store, suppliers


def lines(book: dict) -> list:
    """(item, packs) for every item that needs an order, in catalog order. Planned bakes take their share first."""
    planned = planning.planned_needs(book)
    out = []
    for item in catalog.ITEMS:
        stock = store.available(book, item.name) - planned.get(item.name, 0)
        packs = suppliers.packs_for(item.name, item.supplier, catalog.shortfall(item, stock))
        if packs:
            out.append((item, packs))
    return out
