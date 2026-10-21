"""Quantities. The program keeps every quantity as a whole number in its item's base unit: grams (g), millilitres
(ml) or units (un, for eggs). Only this module turns text into quantities and quantities into text."""
import re
from decimal import ROUND_HALF_UP, Decimal

from .errors import PantryError

# unit typed -> (base unit, how many base units it holds)
UNITS = {"g": ("g", 1), "kg": ("g", 1000), "ml": ("ml", 1), "l": ("ml", 1000), "un": ("un", 1)}
LARGE = {"g": "kg", "ml": "l"}


def parse(text: str, base: str) -> int:
    """'2.5kg' or '2.5 kg' -> 2500 for an item kept in grams. Halves of a base unit round up."""
    found = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([a-z]+)", text.strip().lower())
    if not found:
        raise PantryError(f"Cannot read the quantity {text!r}: write it like 2.5kg, 500g, 1l or 12un.")
    number, unit = found.groups()
    if unit not in UNITS or UNITS[unit][0] != base:
        raise PantryError(f"{text} is not a quantity in {base}.")
    return int((Decimal(number) * UNITS[unit][1]).quantize(Decimal(1), ROUND_HALF_UP))


def show(quantity: int, base: str) -> str:
    """How every quantity is printed. From 1,000 g or ml it shows in kg or l, with at most two decimals, halves
    rounded up and no trailing zeros: 750 -> '750 g', 1255 -> '1.26 kg', 25000 -> '25 kg', 30 eggs -> '30 un'."""
    if base in LARGE and abs(quantity) >= 1000:
        value = (Decimal(quantity) / 1000).quantize(Decimal("0.01"), ROUND_HALF_UP).normalize()
        return f"{value:f} {LARGE[base]}"
    return f"{quantity} {base}"
