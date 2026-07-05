"""Provider interface and concurrent registry.

A ``Provider`` knows how to search one operator. The ``Registry`` fans a query
out over every registered provider concurrently (threads — the work is
I/O-bound HTTP) and returns the combined connections plus a per-provider raw
count used in the output's ``meta`` block. Adding the Nth provider is one new
class implementing ``name()`` and ``search()`` plus a ``register()`` call.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Protocol, Tuple

from ..model import Connection, SearchQuery


class Provider(Protocol):
    """Searches one travel operator for connections."""

    def name(self) -> str:  # pragma: no cover - structural typing
        ...

    def search(self, query: SearchQuery) -> List[Connection]:  # pragma: no cover
        ...


class Registry:
    def __init__(self) -> None:
        self._providers: List[Provider] = []

    def register(self, provider: Provider) -> None:
        self._providers.append(provider)

    def search_all(
        self, query: SearchQuery
    ) -> Tuple[List[Connection], Dict[str, int]]:
        """Query all providers in parallel.

        Returns the combined connections and a ``{provider_name: raw_count}``
        map. If a provider raises, the exception propagates (the first one
        encountered while collecting results).
        """
        conns: List[Connection] = []
        counts: Dict[str, int] = {}
        if not self._providers:
            return conns, counts

        with ThreadPoolExecutor(max_workers=len(self._providers)) as pool:
            future_to_provider = {
                pool.submit(p.search, query): p for p in self._providers
            }
            for future, provider in future_to_provider.items():
                result = future.result()  # re-raises any provider error
                conns.extend(result)
                counts[provider.name()] = len(result)

        return conns, counts
