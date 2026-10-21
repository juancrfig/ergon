import unittest

from inventory import units
from inventory.errors import PantryError


class Units(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(units.parse("2.5kg", "g"), 2500)
        self.assertEqual(units.parse("500 g", "g"), 500)
        self.assertEqual(units.parse("1.0005kg", "g"), 1001)
        self.assertEqual(units.parse("1l", "ml"), 1000)

    def test_parse_wrong_kind(self):
        with self.assertRaises(PantryError):
            units.parse("2l", "g")

    def test_show(self):
        self.assertEqual(units.show(750, "g"), "750 g")
        self.assertEqual(units.show(1255, "g"), "1.26 kg")
        self.assertEqual(units.show(25000, "g"), "25 kg")
        self.assertEqual(units.show(1500, "ml"), "1.5 l")
        self.assertEqual(units.show(30, "un"), "30 un")
