import unittest

from hermes_search.model import Connection, SearchQuery
from hermes_search.providers.base import Registry


class StubProvider:
    def __init__(self, name, conns):
        self._name = name
        self._conns = conns

    def name(self):
        return self._name

    def search(self, query):
        return self._conns


class RaisingProvider:
    def name(self):
        return "boom"

    def search(self, query):
        raise RuntimeError("provider failed")


class RegistryTest(unittest.TestCase):
    def test_search_all_aggregates_and_counts(self):
        reg = Registry()
        reg.register(StubProvider("A", [Connection(provider="A"), Connection(provider="A")]))
        reg.register(StubProvider("B", [Connection(provider="B")]))

        conns, counts = reg.search_all(SearchQuery())
        self.assertEqual(len(conns), 3)
        self.assertEqual(counts, {"A": 2, "B": 1})

    def test_search_all_propagates_provider_error(self):
        reg = Registry()
        reg.register(RaisingProvider())
        with self.assertRaises(RuntimeError):
            reg.search_all(SearchQuery())


if __name__ == "__main__":
    unittest.main()
