"""Currency normalization to EUR.

v1 is an identity seam: every supported provider already reports EUR, so this
maps ``Connection.price_from`` straight onto ``Option.price_eur``. When a
non-EUR provider is added, real FX conversion belongs here (and nowhere else).
"""

from __future__ import annotations

from typing import Iterable, List

from .model import Connection, Option


def to_eur(conn: Connection) -> Option:
    """Wrap a Connection as an Option with its EUR price (identity in v1)."""
    return Option(connection=conn, price_eur=conn.price_from)


def to_eur_all(conns: Iterable[Connection]) -> List[Option]:
    """Map ``to_eur`` over a sequence, preserving order."""
    return [to_eur(c) for c in conns]
