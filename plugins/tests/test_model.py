import unittest

from plugins.hermes_search.model import (
    DEFAULT_FROM_LOCATION_ID,
    DEFAULT_RESULT_COUNT,
    DEFAULT_TO_LOCATION_ID,
    Connection,
    Option,
    SearchQuery,
)


class WithDefaultsTest(unittest.TestCase):
    def test_fills_empty_fields(self):
        got = SearchQuery().with_defaults()
        self.assertEqual(got.from_location_id, DEFAULT_FROM_LOCATION_ID)
        self.assertEqual(got.from_location_type, "CITY")
        self.assertEqual(got.to_location_id, DEFAULT_TO_LOCATION_ID)
        self.assertEqual(got.to_location_type, "STATION")
        self.assertEqual(got.result_count, DEFAULT_RESULT_COUNT)

    def test_keeps_provided_values(self):
        got = SearchQuery(from_location_id="999", result_count=2).with_defaults()
        self.assertEqual(got.from_location_id, "999")
        self.assertEqual(got.result_count, 2)


class OptionJSONTest(unittest.TestCase):
    def test_flat_keys_and_price_eur(self):
        opt = Option(connection=Connection(provider="RegioJet", price_from=16.9), price_eur=16.9)
        data = opt.to_json()
        self.assertEqual(data["provider"], "RegioJet")
        self.assertEqual(data["priceEUR"], 16.9)
        self.assertIn("departureTime", data)
        self.assertEqual(data["departureTime"], None)


if __name__ == "__main__":
    unittest.main()
