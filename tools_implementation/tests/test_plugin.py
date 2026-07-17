import json
import unittest
from datetime import datetime, timezone

from tools_implementation import register, schemas, tools
from tools_implementation.hermes_search.model import Connection
from tools_implementation.hermes_search.providers.base import Registry


class StubProvider:
    def name(self):
        return "RegioJet"

    def search(self, query):
        now = datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone.utc)
        return [
            Connection(provider="RegioJet", price_from=15, bookable=True, free_seats=3, arrival_time=now),
            Connection(provider="RegioJet", price_from=9, bookable=True, free_seats=3, arrival_time=now),
            Connection(provider="RegioJet", price_from=0, bookable=False, free_seats=0, arrival_time=now),
        ]


class SearchConnectionsHandlerTest(unittest.TestCase):
    def setUp(self):
        # Inject a stub provider so the handler never hits the network.
        self._orig_build = tools._build_registry
        registry = Registry()
        registry.register(StubProvider())
        tools._build_registry = lambda: registry

    def tearDown(self):
        tools._build_registry = self._orig_build

    def test_returns_json_string_ranked_cheapest_first(self):
        out = tools.search_connections({"date": "2026-07-08", "limit": 5})
        self.assertIsInstance(out, str)
        data = json.loads(out)
        self.assertEqual([o["priceEUR"] for o in data["options"]], [9, 15])  # sold-out dropped, sorted
        self.assertEqual(data["meta"]["dropped"], 1)
        self.assertEqual(data["meta"]["providersQueried"], ["RegioJet"])

    def test_missing_date_returns_error_json(self):
        data = json.loads(tools.search_connections({}))
        self.assertIn("error", data)

    def test_bad_date_returns_error_json(self):
        data = json.loads(tools.search_connections({"date": "not-a-date"}))
        self.assertIn("error", data)

    def test_naive_arrive_by_returns_error_json(self):
        data = json.loads(tools.search_connections({"date": "2026-07-08", "arrive_by": "2026-07-08T12:00:00"}))
        self.assertIn("error", data)

    def test_always_returns_string_even_on_engine_error(self):
        tools._build_registry = self._raising_registry
        out = tools.search_connections({"date": "2026-07-08"})
        self.assertIsInstance(out, str)
        self.assertIn("error", json.loads(out))

    @staticmethod
    def _raising_registry():
        class Boom:
            def name(self):
                return "boom"

            def search(self, query):
                raise RuntimeError("kaboom")

        reg = Registry()
        reg.register(Boom())
        return reg


class RegisterTest(unittest.TestCase):
    def test_register_wires_schema_to_handler(self):
        calls = []

        class Ctx:
            def register_tool(self, **kwargs):
                calls.append(kwargs)

            def register_hook(self, *args, **kwargs):
                pass

        register(Ctx())

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "search_connections")
        self.assertEqual(calls[0]["toolset"], "hermes_search")
        self.assertIs(calls[0]["handler"], tools.search_connections)
        self.assertIs(calls[0]["schema"], schemas.SEARCH_CONNECTIONS)


if __name__ == "__main__":
    unittest.main()
