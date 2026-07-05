import unittest

from hermes_search.currency import to_eur, to_eur_all
from hermes_search.model import Connection


class CurrencyTest(unittest.TestCase):
    def test_to_eur_uses_price_from(self):
        got = to_eur(Connection(price_from=21.4, price_to=23.1, currency="EUR"))
        self.assertEqual(got.price_eur, 21.4)
        self.assertEqual(got.connection.price_from, 21.4)

    def test_to_eur_all_preserves_order(self):
        got = to_eur_all([Connection(price_from=1), Connection(price_from=2)])
        self.assertEqual([o.price_eur for o in got], [1, 2])


if __name__ == "__main__":
    unittest.main()
