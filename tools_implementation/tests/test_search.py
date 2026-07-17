import unittest
from datetime import datetime, timezone

from tools_implementation.hermes_search import search
from tools_implementation.hermes_search.model import Connection, SearchQuery
from tools_implementation.hermes_search.providers.base import Registry


class StubProvider:
    def name(self):
        return "RegioJet"

    def search(self, query):
        now = datetime(2026, 7, 4, 8, 0, 0, tzinfo=timezone.utc)
        return [
            Connection(provider="RegioJet", price_from=20, bookable=True, free_seats=5, arrival_time=now),
            Connection(provider="RegioJet", price_from=10, bookable=True, free_seats=5, arrival_time=now),
            Connection(provider="RegioJet", price_from=0, bookable=False, free_seats=0, arrival_time=now),
        ]


class SearchPipelineTest(unittest.TestCase):
    def test_run_ranks_and_reports_meta(self):
        reg = Registry()
        reg.register(StubProvider())

        out = search.run(reg, SearchQuery(result_count=5))

        self.assertEqual(len(out["options"]), 2)  # sold-out dropped
        self.assertEqual(out["options"][0]["priceEUR"], 10)  # cheapest first
        self.assertEqual(out["meta"]["rawCount"], 3)
        self.assertEqual(out["meta"]["returned"], 2)
        self.assertEqual(out["meta"]["dropped"], 1)
        self.assertEqual(out["meta"]["providersQueried"], ["RegioJet"])


if __name__ == "__main__":
    unittest.main()
