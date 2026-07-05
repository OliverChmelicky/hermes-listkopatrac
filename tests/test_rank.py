import unittest
from datetime import datetime, timezone

from hermes_search.model import Connection, Option, SearchQuery
from hermes_search.rank import rank


def opt(price, bookable, seats, arrive):
    return Option(
        connection=Connection(
            price_from=price, bookable=bookable, free_seats=seats, arrival_time=arrive
        ),
        price_eur=price,
    )


class RankTest(unittest.TestCase):
    def test_filters_sorts_and_limits(self):
        base = datetime(2026, 7, 4, 8, 0, 0, tzinfo=timezone.utc)
        options = [
            opt(30, True, 5, base),
            opt(0, False, 0, base),  # sold out -> dropped
            opt(10, True, 3, base),
            opt(20, True, 2, base),
            opt(15, True, 0, base),  # no seats -> dropped
        ]
        got = rank(options, SearchQuery(result_count=2))
        self.assertEqual([o.price_eur for o in got], [10, 20])

    def test_applies_arrive_by(self):
        early = datetime(2026, 7, 4, 9, 0, 0, tzinfo=timezone.utc)
        late = datetime(2026, 7, 4, 18, 0, 0, tzinfo=timezone.utc)
        deadline = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        options = [opt(5, True, 1, late), opt(8, True, 1, early)]
        got = rank(options, SearchQuery(result_count=5, arrive_by=deadline))
        self.assertEqual([o.price_eur for o in got], [8])


if __name__ == "__main__":
    unittest.main()
