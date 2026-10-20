"""Hidden tests for split-bill. Each test writes a bill file in a fresh folder and runs the program on it."""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(os.environ.get("EVAL_APP", ".")) / "splitbill.py"
LINE = re.compile(r"^(\S+) pays (\S+) (\d+\.\d\d)$")


class SplitBill(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_bill(self, bill):
        path = Path(self.dir.name) / "bill.json"
        path.write_text(json.dumps(bill))
        return subprocess.run([sys.executable, str(APP), str(path)], cwd=self.dir.name, capture_output=True,
                              text=True, timeout=30)

    def out(self, bill):
        result = self.run_bill(bill)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def error(self, bill):
        result = self.run_bill(bill)
        return result.returncode, result.stderr.strip()

    def test_stated_example_even_split(self):
        bill = {"people": ["Ana", "Ben", "Cy"],
                "expenses": [{"paid_by": "Ana", "amount": "30.00", "for": ["Ana", "Ben", "Cy"]}]}
        self.assertEqual(self.out(bill), "Ben pays Ana 10.00\nCy pays Ana 10.00")

    def test_stated_example_shares(self):
        bill = {"people": ["Ana", "Ben", "Cy"],
                "expenses": [{"paid_by": "Ben", "amount": "12.00", "shares": {"Ana": 50, "Ben": 25, "Cy": 25}}]}
        self.assertEqual(self.out(bill), "Ana pays Ben 6.00\nCy pays Ben 3.00")

    def test_stated_all_settled(self):
        bill = {"people": ["Ana", "Ben", "Cy"],
                "expenses": [{"paid_by": p, "amount": "30.00", "for": ["Ana", "Ben", "Cy"]} for p in ("Ana", "Ben", "Cy")]}
        self.assertEqual(self.out(bill), "All settled.")

    def test_stated_sorted_by_payer_then_receiver(self):
        bill = {"people": ["Ana", "Ben", "Cy"],
                "expenses": [{"paid_by": "Ben", "amount": "10.00", "for": ["Cy"]},
                             {"paid_by": "Ana", "amount": "20.00", "for": ["Cy"]}]}
        self.assertEqual(self.out(bill), "Cy pays Ana 20.00\nCy pays Ben 10.00")

    def test_stated_unknown_payer(self):
        bill = {"people": ["Ana", "Ben"], "expenses": [{"paid_by": "Dan", "amount": "5.00", "for": ["Ana"]}]}
        self.assertEqual(self.error(bill), (1, "Unknown person: Dan"))

    def test_stated_unknown_person_in_for(self):
        bill = {"people": ["Ana", "Ben"], "expenses": [{"paid_by": "Ana", "amount": "5.00", "for": ["Ana", "Bne"]}]}
        self.assertEqual(self.error(bill), (1, "Unknown person: Bne"))

    def test_stated_random_bills_settle_to_the_cent(self):
        rng = random.Random(7)
        names = ["Ana", "Ben", "Cy", "Dee", "Eli", "Fay"]
        for _ in range(25):
            people = names[:rng.randint(2, 6)]
            expenses, net = [], {p: 0 for p in people}
            for _ in range(rng.randint(1, 8)):
                group = rng.sample(people, rng.randint(1, len(people)))
                cents = rng.randint(1, 4000) * len(group)       # divides evenly: no rounding rule involved
                payer = rng.choice(people)
                expenses.append({"paid_by": payer, "amount": f"{cents // 100}.{cents % 100:02d}", "for": group})
                net[payer] += cents
                for p in group:
                    net[p] -= cents // len(group)
            output = self.out({"people": people, "expenses": expenses})
            lines = [] if output == "All settled." else output.splitlines()
            self.assertLessEqual(len(lines), len(people) - 1, output)
            payers, receivers = set(), set()
            for line in lines:
                match = LINE.match(line)
                self.assertIsNotNone(match, line)
                payer, receiver, amount = match.groups()
                cents = int(amount.replace(".", ""))
                self.assertGreater(cents, 0, line)
                net[payer] += cents
                net[receiver] -= cents
                payers.add(payer)
                receivers.add(receiver)
            self.assertEqual(set(net.values()), {0}, f"{expenses}\n{output}")
            self.assertFalse(payers & receivers, output)

    def test_ask_leftover_cents_go_to_the_first_listed(self):
        """F1"""
        bill = {"people": ["Ana", "Ben", "Cy"],
                "expenses": [{"paid_by": "Ben", "amount": "10.00", "for": ["Ana", "Ben", "Cy"]}]}
        self.assertEqual(self.out(bill), "Ana pays Ben 3.34\nCy pays Ben 3.33")

    def test_ask_leftover_cents_follow_the_expense_order(self):
        """F1"""
        bill = {"people": ["Ana", "Ben", "Cy"],
                "expenses": [{"paid_by": "Ben", "amount": "10.00", "for": ["Cy", "Ana", "Ben"]}]}
        self.assertEqual(self.out(bill), "Ana pays Ben 3.33\nCy pays Ben 3.34")

    def test_ask_leftover_cents_in_shares(self):
        """F1"""
        bill = {"people": ["Ana", "Ben", "Cy"],
                "expenses": [{"paid_by": "Ana", "amount": "0.05", "shares": {"Ben": 50, "Cy": 50}}]}
        self.assertEqual(self.out(bill), "Ben pays Ana 0.03\nCy pays Ana 0.02")

    def test_ask_shares_must_add_up_to_100(self):
        """F2"""
        bill = {"people": ["Ana", "Ben"],
                "expenses": [{"paid_by": "Ana", "amount": "10.00", "shares": {"Ana": 50, "Ben": 40}}]}
        self.assertEqual(self.error(bill), (1, "Shares must add up to 100."))
