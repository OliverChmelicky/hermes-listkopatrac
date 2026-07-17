import http.server
import os
import threading
import unittest
from datetime import date

from tools_implementation.hermes_search.model import SearchQuery
from tools_implementation.hermes_search.providers.regiojet import RegioJet

FIXTURE = os.path.join(os.path.dirname(__file__), "testdata", "search_response.json")


class _Handler(http.server.BaseHTTPRequestHandler):
    body = b""
    captured = {}

    def do_GET(self):
        _Handler.captured["path"] = self.path.split("?", 1)[0]
        _Handler.captured["query"] = self.path.split("?", 1)[1] if "?" in self.path else ""
        _Handler.captured["currency"] = self.headers.get("X-Currency")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_Handler.body)

    def log_message(self, *args):  # silence test server logging
        pass


class RegioJetTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, "rb") as fh:
            _Handler.body = fh.read()
        _Handler.captured = {}
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_search_maps_routes(self):
        client = RegioJet(base_url=self.base_url)
        query = SearchQuery(departure_date=date(2026, 7, 3)).with_defaults()
        conns = client.search(query)

        self.assertEqual(_Handler.captured["path"], "/routes/search/simple")
        self.assertEqual(_Handler.captured["currency"], "EUR")
        self.assertIn("departureDate=2026-07-03", _Handler.captured["query"])
        self.assertTrue(conns, "expected connections mapped")

        # First fixture route is sold out: priceFrom 0, not bookable, no seats.
        first = conns[0]
        self.assertFalse(first.bookable)
        self.assertEqual(first.price_from, 0)
        self.assertEqual(first.free_seats, 0)
        self.assertEqual(first.provider, "RegioJet")
        self.assertEqual(first.currency, "EUR")

        # At least one bookable route with a real price and sane times.
        bookable = [c for c in conns if c.bookable and c.price_from > 0]
        self.assertTrue(bookable, "expected at least one bookable route")
        for c in bookable:
            self.assertGreater(c.arrival_time, c.departure_time)


if __name__ == "__main__":
    unittest.main()
