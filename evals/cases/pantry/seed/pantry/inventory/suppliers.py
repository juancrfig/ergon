"""Who sells the bakery each item, and in what packs."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Supplier:
    name: str
    min_packs: int   # the supplier's minimum order, in packs of one item


SUPPLIERS = {
    "molinos": Supplier("Molinos Andinos", 1),
    "dulce": Supplier("Dulce Valle", 3),
    "lacteos": Supplier("Lacteos La Vega", 2),
    "granja": Supplier("Granja El Roble", 2),
}

# item -> pack size, in the item's base unit
PACKS = {"flour": 25000, "sugar": 10000, "butter": 1000, "milk": 1000, "eggs": 30, "yeast": 500}


def packs_for(item: str, supplier: str, quantity: int) -> int:
    """Packs to order to bring in at least `quantity`: whole packs only, rounded up, and never fewer than the
    supplier's minimum order. Nothing to bring in means no packs."""
    if quantity <= 0:
        return 0
    return max(-(-quantity // PACKS[item]), SUPPLIERS[supplier].min_packs)
