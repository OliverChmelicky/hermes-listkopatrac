"""Filter, sort, and limit search options.

Ranking rules (in order):

1. Drop options that are not bookable, have no free seats, or have no price
   (RegioJet reports sold-out routes with ``priceFrom == 0``).
2. When the query has an ``arrive_by`` deadline, drop options arriving after it.
   This is done here (client-side) because RegioJet's simple search only accepts
   a departure *day*, not a target arrival time.
3. Sort the survivors by EUR price ascending.
4. Return at most ``query.result_count`` of them.
"""

from __future__ import annotations

from typing import List

from .model import Option, SearchQuery


def rank(options: List[Option], query: SearchQuery) -> List[Option]:
    kept: List[Option] = []
    for opt in options:
        c = opt.connection
        if not c.bookable or c.free_seats <= 0 or c.price_from <= 0:
            continue
        if (
            query.arrive_by is not None
            and c.arrival_time is not None
            and c.arrival_time > query.arrive_by
        ):
            continue
        kept.append(opt)

    kept.sort(key=lambda o: o.price_eur)

    if query.result_count and query.result_count > 0:
        kept = kept[: query.result_count]
    return kept
