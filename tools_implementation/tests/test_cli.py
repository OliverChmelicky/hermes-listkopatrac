import unittest
from datetime import date, datetime

from tools_implementation.hermes_search.cli import build_parser, build_query


class BuildQueryTest(unittest.TestCase):
    def test_parses_flags_into_query(self):
        args = build_parser().parse_args(
            ["--date", "2026-07-03", "--from", "111", "--to", "222", "--limit", "3"]
        )
        q = build_query(args)
        self.assertEqual(q.departure_date, date(2026, 7, 3))
        self.assertEqual(q.from_location_id, "111")
        self.assertEqual(q.to_location_id, "222")
        self.assertEqual(q.result_count, 3)

    def test_defaults_applied_when_omitted(self):
        args = build_parser().parse_args(["--date", "2026-07-03"])
        q = build_query(args)
        self.assertEqual(q.from_location_id, "10202001")
        self.assertEqual(q.to_location_id, "372825000")
        self.assertEqual(q.result_count, 5)

    def test_parses_arrive_by(self):
        args = build_parser().parse_args(
            ["--date", "2026-07-03", "--arrive-by", "2026-07-03T18:00:00+02:00"]
        )
        q = build_query(args)
        self.assertIsInstance(q.arrive_by, datetime)
        self.assertIsNotNone(q.arrive_by.tzinfo)

    def test_bad_date_raises_value_error(self):
        args = build_parser().parse_args(["--date", "not-a-date"])
        with self.assertRaises(ValueError):
            build_query(args)


if __name__ == "__main__":
    unittest.main()
