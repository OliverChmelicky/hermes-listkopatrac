"""RegioJet provider adapter.

Queries RegioJet's public route-search endpoint and maps **every** returned
route (including sold-out ones, which come back with ``priceFrom == 0``) into a
``Connection``. Filtering is the ranker's job, not the adapter's. Prices are
requested in EUR via the ``X-Currency`` header so output is deterministic.

Endpoint: ``GET {base_url}/routes/search/simple`` with query params
``fromLocationId/Type``, ``toLocationId/Type``, ``departureDate`` (YYYY-MM-DD),
``tariffs=REGULAR``.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from typing import List

from ..model import Connection, SearchQuery

DEFAULT_BASE_URL = "https://brn-ybus-pubapi.sa.cz/restapi"


class RegioJet:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def name(self) -> str:
        return "RegioJet"

    def search(self, query: SearchQuery) -> List[Connection]:
        params = {
            "tariffs": "REGULAR",
            "fromLocationType": query.from_location_type,
            "fromLocationId": query.from_location_id,
            "toLocationType": query.to_location_type,
            "toLocationId": query.to_location_id,
            "departureDate": query.departure_date.strftime("%Y-%m-%d"),
            "fromLocationName": "",
            "toLocationName": "",
        }
        url = self.base_url + "/routes/search/simple?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={"X-Currency": "EUR", "Accept": "application/json"},
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            status = getattr(resp, "status", resp.getcode())
            if status != 200:
                raise RuntimeError(f"regiojet: status {status}")
            payload = json.load(resp)

        conns: List[Connection] = []
        for r in payload.get("routes", []):
            conns.append(
                Connection(
                    provider="RegioJet",
                    departure_time=datetime.fromisoformat(r["departureTime"]),
                    arrival_time=datetime.fromisoformat(r["arrivalTime"]),
                    price_from=float(r.get("priceFrom") or 0.0),
                    price_to=float(r.get("priceTo") or 0.0),
                    currency="EUR",
                    free_seats=int(r.get("freeSeatsCount") or 0),
                    transfers=int(r.get("transfersCount") or 0),
                    travel_time=r.get("travelTime", ""),
                    bookable=bool(r.get("bookable", False)),
                )
            )
        return conns
