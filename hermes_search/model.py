"""Shared data types for the Hermes search tool.

These structures are provider-agnostic:

- ``SearchQuery`` is the structured form of the request the agent passes in.
  ``with_defaults()`` fills any unset field from the example RegioJet route.
- ``Connection`` is one option exactly as a provider returns it, priced in the
  provider's own currency.
- ``Option`` wraps a ``Connection`` with a EUR-normalized price. Ranking and the
  JSON output work on ``Option``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

# Defaults taken from the sample RegioJet request (used when the agent omits a
# location or a result count).
DEFAULT_FROM_LOCATION_ID = "10202001"
DEFAULT_FROM_LOCATION_TYPE = "CITY"
DEFAULT_TO_LOCATION_ID = "372825000"
DEFAULT_TO_LOCATION_TYPE = "STATION"
DEFAULT_RESULT_COUNT = 5


@dataclass
class SearchQuery:
    """A validated travel request. Times use ``date``/``datetime``."""

    from_location_id: str = ""
    from_location_type: str = ""
    to_location_id: str = ""
    to_location_type: str = ""
    departure_date: Optional[date] = None  # day granularity
    arrive_by: Optional[datetime] = None  # optional deadline at destination
    result_count: int = 0

    def with_defaults(self) -> "SearchQuery":
        """Return a copy with empty fields filled from the module defaults."""
        return SearchQuery(
            from_location_id=self.from_location_id or DEFAULT_FROM_LOCATION_ID,
            from_location_type=self.from_location_type or DEFAULT_FROM_LOCATION_TYPE,
            to_location_id=self.to_location_id or DEFAULT_TO_LOCATION_ID,
            to_location_type=self.to_location_type or DEFAULT_TO_LOCATION_TYPE,
            departure_date=self.departure_date,
            arrive_by=self.arrive_by,
            result_count=self.result_count or DEFAULT_RESULT_COUNT,
        )


@dataclass
class Connection:
    """One connection option in the provider's own currency."""

    provider: str = ""
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    price_from: float = 0.0
    price_to: float = 0.0
    currency: str = ""
    free_seats: int = 0
    transfers: int = 0
    travel_time: str = ""
    bookable: bool = False


@dataclass
class Option:
    """A ``Connection`` plus its EUR-normalized price, ready for ranking."""

    connection: Connection
    price_eur: float = 0.0

    def to_json(self) -> dict:
        """Flat JSON dict (camelCase keys) for the tool's stdout output."""
        c = self.connection
        return {
            "provider": c.provider,
            "departureTime": c.departure_time.isoformat() if c.departure_time else None,
            "arrivalTime": c.arrival_time.isoformat() if c.arrival_time else None,
            "priceFrom": c.price_from,
            "priceTo": c.price_to,
            "currency": c.currency,
            "freeSeats": c.free_seats,
            "transfers": c.transfers,
            "travelTime": c.travel_time,
            "bookable": c.bookable,
            "priceEUR": self.price_eur,
        }


# Convenience alias for type hints elsewhere.
Connections = List[Connection]
Options = List[Option]
