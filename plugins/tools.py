"""Tool handlers — the code that runs when the LLM calls each tool.

Each handler follows the plugin contract:
1. Receives ``args`` (dict) — the parameters the LLM passed.
2. Does the work (here: builds a SearchQuery and runs the search pipeline).
3. Returns a JSON string — ALWAYS, even on error.
4. Accepts ``**kwargs`` for forward compatibility.

The actual search logic lives in the ``hermes_search`` engine subpackage; this
module is only the thin plugin adapter over it.
"""

import json
from datetime import datetime

from .hermes_search import search
from .hermes_search.model import SearchQuery
from .hermes_search.providers.base import Registry
from .hermes_search.providers.regiojet import RegioJet


def _build_registry() -> Registry:
    """Build the provider registry. Patched in tests to avoid network calls."""
    registry = Registry()
    registry.register(RegioJet())
    return registry


def search_connections(args: dict, **kwargs) -> str:
    """Search RegioJet for A→B connections; return ranked EUR options as JSON."""
    date_str = str(args.get("date") or "").strip()
    if not date_str:
        return json.dumps({"error": "Missing required 'date' (YYYY-MM-DD)"})

    try:
        departure_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return json.dumps({"error": f"Invalid 'date' {date_str!r}, expected YYYY-MM-DD"})

    arrive_by = None
    arrive_by_str = str(args.get("arrive_by") or "").strip()
    if arrive_by_str:
        try:
            arrive_by = datetime.fromisoformat(arrive_by_str)
        except ValueError:
            return json.dumps(
                {"error": f"Invalid 'arrive_by' {arrive_by_str!r}, expected ISO 8601 with offset"}
            )
        if arrive_by.tzinfo is None:
            return json.dumps(
                {"error": "'arrive_by' must include a UTC offset, e.g. 2026-07-08T18:00:00+02:00"}
            )

    try:
        limit = int(args.get("limit") or 0)
    except (TypeError, ValueError):
        return json.dumps({"error": f"Invalid 'limit' {args.get('limit')!r}, expected an integer"})

    query = SearchQuery(
        from_location_id=str(args.get("from_location_id") or ""),
        from_location_type=str(args.get("from_location_type") or ""),
        to_location_id=str(args.get("to_location_id") or ""),
        to_location_type=str(args.get("to_location_type") or ""),
        departure_date=departure_date,
        arrive_by=arrive_by,
        result_count=limit,
    ).with_defaults()

    try:
        result = search.run(_build_registry(), query)
    except Exception as exc:  # network/parse errors -> error JSON, never raise
        return json.dumps({"error": f"Search failed: {exc}"})

    return json.dumps(result)
