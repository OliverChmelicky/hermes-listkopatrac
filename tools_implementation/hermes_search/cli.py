"""Command-line entry point for the Hermes search tool.

The Hermes agent calls this as a CLI binary:

    python -m hermes_search --date 2026-07-03 [--from ID] [--to ID] \
        [--from-type CITY|STATION] [--to-type CITY|STATION] \
        [--arrive-by 2026-07-03T18:00:00+02:00] [--limit 5]

It parses flags into a ``SearchQuery``, runs the pipeline, and prints a single
JSON object to stdout. Bad input or a provider error is reported on stderr with
a non-zero exit code (2 = bad flags, 1 = search/transport error).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import List, Optional

from . import search
from .model import SearchQuery
from .providers.base import Registry
from .providers.regiojet import RegioJet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hermes-search",
        description="Search RegioJet for A->B connections; print ranked EUR options as JSON.",
    )
    parser.add_argument("--date", required=True, help="departure day YYYY-MM-DD")
    parser.add_argument("--from", dest="from_", default="", help="from location ID (default 10202001)")
    parser.add_argument("--from-type", dest="from_type", default="", help="CITY|STATION (default CITY)")
    parser.add_argument("--to", dest="to", default="", help="to location ID (default 372825000)")
    parser.add_argument("--to-type", dest="to_type", default="", help="CITY|STATION (default STATION)")
    parser.add_argument("--arrive-by", dest="arrive_by", default="", help="arrival deadline, ISO 8601 with offset")
    parser.add_argument("--limit", dest="limit", type=int, default=0, help="max options to return (default 5)")
    return parser


def build_query(args: argparse.Namespace) -> SearchQuery:
    """Turn parsed args into a SearchQuery. Raises ValueError on bad dates."""
    departure_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    arrive_by = None
    if args.arrive_by:
        arrive_by = datetime.fromisoformat(args.arrive_by)

    return SearchQuery(
        from_location_id=args.from_,
        from_location_type=args.from_type,
        to_location_id=args.to,
        to_location_type=args.to_type,
        departure_date=departure_date,
        arrive_by=arrive_by,
        result_count=args.limit,
    ).with_defaults()


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        query = build_query(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    registry = Registry()
    registry.register(RegioJet())

    try:
        output = search.run(registry, query)
    except Exception as exc:  # network/parse errors -> stderr, non-zero exit
        print(f"error: {exc}", file=sys.stderr)
        return 1

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
