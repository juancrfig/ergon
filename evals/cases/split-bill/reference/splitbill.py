"""Settle a shared bill. Run: python3 splitbill.py <bill file>."""
import json
import sys
from decimal import Decimal
from pathlib import Path


class BillError(Exception):
    pass


def cents(amount: str) -> int:
    return int(Decimal(amount) * 100)


def parts(total: int, weights: dict) -> dict:
    """Each person's part in cents: rounded down, then the leftover cents one each, in the order given."""
    whole = sum(weights.values())
    out = {p: total * w // whole for p, w in weights.items()}
    for person in list(weights)[:total - sum(out.values())]:
        out[person] += 1
    return out


def balances(bill: dict) -> dict:
    people = bill["people"]
    net = {p: 0 for p in people}
    for expense in bill["expenses"]:
        if "shares" in expense:
            weights = dict(expense["shares"])
            if sum(weights.values()) != 100:
                raise BillError("Shares must add up to 100.")
        else:
            weights = {p: 1 for p in expense["for"]}
        for person in [expense["paid_by"], *weights]:
            if person not in net:
                raise BillError(f"Unknown person: {person}")
        total = cents(expense["amount"])
        net[expense["paid_by"]] += total
        for person, part in parts(total, weights).items():
            net[person] -= part
    return net


def settle(net: dict) -> list:
    """Largest debtor pays largest creditor until all are even: at most one payment fewer than people."""
    net, payments = dict(net), []
    while True:
        debtor = min(net, key=lambda p: (net[p], p))
        creditor = max(net, key=lambda p: (net[p], p))
        if net[debtor] == 0:
            return payments
        amount = min(-net[debtor], net[creditor])
        payments.append((debtor, creditor, amount))
        net[debtor] += amount
        net[creditor] -= amount


def main(path: str) -> int:
    try:
        payments = settle(balances(json.loads(Path(path).read_text())))
    except BillError as exc:
        print(exc, file=sys.stderr)
        return 1
    lines = [f"{a} pays {b} {c // 100}.{c % 100:02d}" for a, b, c in sorted(payments)]
    print("\n".join(lines) or "All settled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
