"""The search pipeline: fan out, normalize to EUR, rank, assemble output.

``run()`` returns a plain ``dict`` ready to serialize to JSON:

- ``options``: the ranked list (cheapest EUR first), each a flat option dict.
- ``meta``: how the search was performed, so the agent can narrate the process
  (which providers were queried, how many raw routes came back, how many were
  dropped by filtering, how many are returned).
"""

from __future__ import annotations

from typing import Any, Dict

from . import currency, rank
from .model import SearchQuery
from .providers.base import Registry


def run(registry: Registry, query: SearchQuery) -> Dict[str, Any]:
    conns, counts = registry.search_all(query)
    options = currency.to_eur_all(conns)
    ranked = rank.rank(options, query)

    return {
        "options": [opt.to_json() for opt in ranked],
        "meta": {
            "providersQueried": sorted(counts.keys()),
            "providerRaw": counts,
            "rawCount": len(conns),
            "dropped": len(conns) - len(ranked),
            "returned": len(ranked),
        },
    }
