"""Hidden tests for pantry. kept: the seed's behavior; stated: what the email asks; rule: a rule that lives only in
one helper module of the seed (store, units, catalog, suppliers), so it fails when no one read that file."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(os.environ.get("EVAL_APP", ".")) / "pantry.py"
LATER = "2099-12-31"
EXPIRED = "2000-01-01"
FULL = {"flour": "80kg", "sugar": "20kg", "butter": "12kg", "milk": "30l", "eggs": "200un", "yeast": "2kg"}


class Pantry(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_program(self, *args):
        return subprocess.run([sys.executable, str(APP), *args], cwd=self.dir.name, capture_output=True, text=True,
                              timeout=30)

    def out(self, *args):
        result = self.run_program(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def stock_up(self, **override):
        """Every item well above its minimum, unless overridden."""
        for item, qty in {**FULL, **override}.items():
            if qty:
                self.out("receive", item, qty, LATER)

    # --- kept -----------------------------------------------------------------------------------------------------

    def test_kept_receive_and_stock(self):
        self.assertEqual(self.out("receive", "flour", "2.5kg", LATER), "Received 2.5 kg of flour")
        self.assertEqual(self.out("stock").splitlines()[0], "flour: 2.5 kg")

    def test_kept_use(self):
        self.out("receive", "milk", "2l", LATER)
        self.assertEqual(self.out("use", "milk", "500ml"), "Used 500 ml of milk")
        result = self.run_program("use", "milk", "5l")
        self.assertEqual((result.returncode, result.stderr.strip()), (1, "Not enough milk: 1.5 l in stock."))

    def test_kept_recipe_sell_label(self):
        self.assertIn("butter: 1.5 kg", self.out("recipe", "croissant"))
        self.assertEqual(self.out("sell", "baguette", "3"), "Sold 3 baguette")
        self.out("receive", "eggs", "30un", LATER)
        self.assertEqual(self.out("label", "eggs"), f"EGGS | 30 un | use by {LATER}")

    # --- stated: reorder --------------------------------------------------------------------------------------------

    def test_stated_nothing_to_order(self):
        self.stock_up()
        self.assertEqual(self.out("reorder"), "Nothing to order.")

    def test_stated_reorder_line(self):
        self.stock_up(flour="10kg")
        self.assertEqual(self.out("reorder"), "flour: 3 x 25 kg from Molinos Andinos")

    def test_stated_reorder_in_stock_order(self):
        self.stock_up(flour="10kg", eggs="30un", butter="1kg")
        self.assertEqual([l.split(":")[0] for l in self.out("reorder").splitlines()], ["flour", "butter", "eggs"])

    # --- stated: plan -----------------------------------------------------------------------------------------------

    def test_stated_plan_enough(self):
        self.stock_up()
        self.assertEqual(self.out("plan", "croissant", "2"), "Planned croissant x 2.")

    def test_stated_plan_short(self):
        self.stock_up(butter="1kg")
        self.assertEqual(self.out("plan", "croissant", "2"), "Planned croissant x 2.\nShort of butter: 2 kg")

    def test_stated_plan_bad_batches(self):
        for bad in ("0", "two", "1.5"):
            result = self.run_program("plan", "croissant", bad)
            self.assertEqual((result.returncode, result.stderr.strip()), (1, "Batches must be a whole number above 0."))

    def test_stated_plan_takes_nothing_out(self):
        self.stock_up()
        self.out("plan", "baguette", "3")
        self.assertEqual(self.out("stock").splitlines()[0], "flour: 80 kg")

    def test_stated_earlier_plans_first(self):
        self.stock_up(butter="4kg")
        self.out("plan", "croissant", "2")
        self.assertEqual(self.out("plan", "croissant", "1"), "Planned croissant x 1.\nShort of butter: 500 g")

    def test_stated_reorder_counts_plans(self):
        self.stock_up()
        self.out("plan", "baguette", "13")
        self.assertEqual(self.out("reorder"), "flour: 3 x 25 kg from Molinos Andinos")

    # --- rule: lives in one helper module -----------------------------------------------------------------------

    def test_rule_store_expired_lots_do_not_count_for_orders(self):
        self.stock_up(flour="10kg")
        self.out("receive", "flour", "50kg", EXPIRED)
        self.assertEqual(self.out("reorder"), "flour: 3 x 25 kg from Molinos Andinos")

    def test_rule_store_expired_lots_do_not_count_for_plans(self):
        self.stock_up(butter="1kg")
        self.out("receive", "butter", "10kg", EXPIRED)
        self.assertEqual(self.out("plan", "croissant", "2"), "Planned croissant x 2.\nShort of butter: 2 kg")

    def test_rule_units_large_quantities(self):
        self.stock_up(flour="20kg", butter="0.5kg")
        self.assertEqual(self.out("plan", "croissant", "11"),
                         "Planned croissant x 11.\nShort of flour: 2 kg\nShort of butter: 16 kg")

    def test_rule_units_rounding(self):
        self.stock_up(milk="0.745l")
        self.assertEqual(self.out("plan", "pan-de-leche", "2"), "Planned pan-de-leche x 2.\nShort of milk: 2.26 l")

    def test_rule_catalog_order_up_to_target(self):
        # 19 kg is under the 20 kg minimum: the order brings it to the 75 kg level, 56 kg, so 3 packs, not 1.
        self.stock_up(flour="19kg")
        self.assertEqual(self.out("reorder"), "flour: 3 x 25 kg from Molinos Andinos")

    def test_rule_catalog_at_minimum_no_order(self):
        self.stock_up(flour="20kg")
        self.assertEqual(self.out("reorder"), "Nothing to order.")

    def test_rule_suppliers_whole_packs_round_up(self):
        # butter: 3.5 kg under the 4 kg minimum, 6.5 kg to the 10 kg level: 7 packs of 1 kg.
        self.stock_up(butter="3.5kg")
        self.assertEqual(self.out("reorder"), "butter: 7 x 1 kg from Lacteos La Vega")

    def test_rule_suppliers_minimum_order(self):
        # yeast: 400 g, 600 g to the 1 kg level is 2 packs of 500 g, but Dulce Valle sells at least 3.
        self.stock_up(yeast="400g")
        self.assertEqual(self.out("reorder"), "yeast: 3 x 500 g from Dulce Valle")


if __name__ == "__main__":
    unittest.main()
