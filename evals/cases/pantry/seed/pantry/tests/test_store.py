import unittest

from inventory import catalog, store, suppliers


class Store(unittest.TestCase):
    def book(self):
        return {"lots": [{"item": "flour", "qty": 5000, "expires": "2000-01-01"},
                         {"item": "flour", "qty": 3000, "expires": "2099-01-01"},
                         {"item": "flour", "qty": 2000, "expires": "2098-01-01"}], "sales": []}

    def test_expired_lots_do_not_count(self):
        self.assertEqual(store.available(self.book(), "flour", "2026-10-01"), 5000)

    def test_take_uses_the_first_to_expire(self):
        book = self.book()
        store.take(book, "flour", 2500, "2026-10-01")
        self.assertEqual([l["qty"] for l in book["lots"]], [5000, 2500])


class Rules(unittest.TestCase):
    def test_shortfall(self):
        flour = catalog.get("flour")
        self.assertEqual(catalog.shortfall(flour, 20000), 0)
        self.assertEqual(catalog.shortfall(flour, 19999), 55001)

    def test_packs(self):
        self.assertEqual(suppliers.packs_for("flour", "molinos", 55001), 3)
        self.assertEqual(suppliers.packs_for("yeast", "dulce", 700), 3)
        self.assertEqual(suppliers.packs_for("yeast", "dulce", 0), 0)
