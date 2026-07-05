# Hermes Search Tool — Design

**Date:** 2026-07-03
**Status:** Implemented (Python)

## Overview

Hermes is an LLM agent that the user sets up and runs themselves. It reads the
`skills/*.md` policy, talks to the user, asks for missing details, decides when
to search, and narrates results — **all of that lives in the agent, not in this
project.**

This project builds **one tool the Hermes agent invokes: a Python CLI that
searches a travel provider (RegioJet) for connections A→B and returns ranked,
EUR-priced results as JSON on stdout.** The agent shells out to the tool and
narrates the JSON it gets back.

> Originally scoped in Go; the machine has no Go toolchain, so it was
> implemented in Python 3 (stdlib only). The CLI contract and JSON output are
> language-independent and unchanged.

## Goals

- A single, dependency-free Python CLI the agent calls with flags.
- Query a provider for connections A→B on a given day, honoring an optional
  "arrive by" deadline.
- Filter unavailable options, rank the rest by price in EUR, return the best N.
- Emit structured JSON (results + a small "how it searched" meta block) so the
  agent can both list options and describe the process.
- A description file in `tools/` so the Hermes agent knows how to call it.

## Non-goals (this project)

The following belong to the **Hermes agent**, not to this tool:

- **No LLM in the tool.** No intake parsing, no clarifying questions, no result
  narration. The agent does all natural-language work.
- **No conversation/orchestration.** The tool is one-shot: flags in, JSON out.
- **No Telegram/CLI chat loop.** The agent owns the user channel.
- **No city→station-ID resolution.** The agent passes IDs (or omits them for
  defaults). Plain city names are not resolved here.
- **No real currency conversion.** RegioJet prices are already EUR; the
  converter is an identity seam until a non-EUR provider is added.
- **No booking.** Search and recommendation only.
- Only RegioJet. České dráhy and Leo Express are future providers.

## Architecture

A small Python package with a clear split:

- **`cli`** — parses flags into a `SearchQuery`, runs the pipeline, prints JSON,
  sets an exit code.
- **`search`** — the pipeline: fan out over providers, normalize to EUR, rank,
  and assemble the output dict (options + meta). Pure and testable.
- **`providers.base`** — a `Provider` protocol and a concurrent `Registry`, so
  adding the Nth provider is one new class.
- **`providers.regiojet`** — the one adapter, against the known REST endpoint.
- **`currency`**, **`rank`**, **`model`** — supporting units.

```
flags ──▶ SearchQuery ──▶ search.run:
                             registry.search_all (threads, concurrent)
                                 │
                                 ▼
                             currency.to_eur_all → EUR (identity seam)
                                 │
                                 ▼
                             rank.rank: filter + sort + take N
                                 │
                                 ▼
                             {options, meta} ──▶ JSON to stdout
```

### Package layout

```
hermes-search                     executable wrapper (python -m hermes_search)
hermes_search/
  __init__.py                     package docstring
  __main__.py                     enables `python -m hermes_search`
  cli.py                          flags → pipeline → JSON out
  search.py                       pipeline: fan-out + currency + rank + assemble
  currency.py                     provider price → EUR (identity seam)
  rank.py                         filter + sort + take N (pure)
  model.py                        SearchQuery, Connection, Option (dataclasses)
  providers/
    __init__.py
    base.py                       Provider protocol + concurrent Registry
    regiojet.py                   RegioJet adapter (urllib)
tests/                            unittest suite + testdata/ fixture
tools/hermes-search.md            tool description for the agent
```

## CLI contract

Invocation: `python -m hermes_search` (or `./hermes-search`).

Flags:

| Flag          | Meaning                              | Default            |
|---------------|--------------------------------------|--------------------|
| `--date`      | departure day `YYYY-MM-DD`           | **required**       |
| `--from`      | from location ID                     | `10202001`         |
| `--from-type` | `CITY` or `STATION`                  | `CITY`             |
| `--to`        | to location ID                       | `372825000`        |
| `--to-type`   | `CITY` or `STATION`                  | `STATION`          |
| `--arrive-by` | ISO 8601 (with offset) deadline      | none (optional)    |
| `--limit`     | max options to return                | `5`                |

Output: a single JSON object on stdout:

```json
{
  "options": [
    {
      "provider": "RegioJet",
      "departureTime": "2026-07-08T05:17:00+02:00",
      "arrivalTime": "2026-07-08T09:58:00+02:00",
      "priceFrom": 11.9,
      "priceTo": 25.9,
      "currency": "EUR",
      "freeSeats": 299,
      "transfers": 0,
      "travelTime": "04:41 h",
      "bookable": true,
      "priceEUR": 11.9
    }
  ],
  "meta": {
    "providersQueried": ["RegioJet"],
    "providerRaw": { "RegioJet": 24 },
    "rawCount": 24,
    "dropped": 21,
    "returned": 3
  }
}
```

Exit codes: `0` on success (even with zero options); `2` for bad/missing flags;
`1` for a provider/transport error (message on stderr).

## Core types (`model.py`)

```python
@dataclass
class SearchQuery:
    from_location_id: str = ""
    from_location_type: str = ""
    to_location_id: str = ""
    to_location_type: str = ""
    departure_date: date | None = None
    arrive_by: datetime | None = None
    result_count: int = 0
    def with_defaults(self) -> "SearchQuery": ...

@dataclass
class Connection:
    provider: str = ""
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    price_from: float = 0.0
    price_to: float = 0.0
    currency: str = ""
    free_seats: int = 0
    transfers: int = 0
    travel_time: str = ""
    bookable: bool = False

@dataclass
class Option:
    connection: Connection
    price_eur: float = 0.0
    def to_json(self) -> dict: ...  # flat camelCase dict for stdout
```

## Pipeline flow (`search.run`)

1. `Registry.search_all` fans out over all registered providers concurrently
   (threads; RegioJet only today; loop is N-ready) → connections + per-provider
   raw counts.
2. `currency.to_eur_all` → options with `price_eur` (identity in v1).
3. `rank.rank`: drop unbookable, `free_seats == 0`, sold-out (`price_from == 0`);
   drop anything arriving after `arrive_by` when set; sort by `price_eur` asc;
   take `result_count`.
4. Assemble `{options, meta}`; `meta.dropped = rawCount - returned`.

The **"arrive by" filter is client-side** because RegioJet's `search/simple`
endpoint only accepts a departure *day*, not a target arrival time.

## RegioJet adapter

- **Endpoint:** `GET https://brn-ybus-pubapi.sa.cz/restapi/routes/search/simple`
- **Params:** `fromLocationId`, `fromLocationType`, `toLocationId`,
  `toLocationType`, `departureDate` (YYYY-MM-DD), `tariffs=REGULAR`,
  `fromLocationName=`, `toLocationName=` (empty).
- **Defaults:** `fromLocationId=10202001` (CITY), `toLocationId=372825000`
  (STATION) when the query leaves them empty.
- **Currency:** sends header `X-Currency: EUR` so prices are deterministic.
- **Response mapping:** `routes[]` → `Connection`; times parsed with
  `datetime.fromisoformat`. The adapter maps **every** route (including sold-out
  ones with `priceFrom: 0`); filtering is `rank`'s job.

## Tool description (`tools/hermes-search.md`)

A markdown file the Hermes agent reads to learn the tool: what it does, the exact
command with an example, the flag meanings, and the JSON output shape.

## Extensibility

- **Add a provider:** new class implementing `name()`/`search()`, register it in
  the pipeline's registry. Fan-out picks it up with no other changes.
- **Add another tool for the agent:** a separate module/command + its own
  `tools/*.md` description; independent of this one.

## Confirmed assumptions

1. Hermes (the agent) is set up and run by the user; this project delivers only
   the CLI search tool it calls.
2. The agent invokes the tool as a **CLI** (flags in, JSON out).
3. RegioJet prices are EUR; `currency.to_eur` is an identity seam in v1.
4. City→station-ID resolution is out of scope; IDs are provided or default to
   the example.

## Future work

- Additional providers (České dráhy, Leo Express) via new adapters.
- Real currency conversion with an FX source when a non-EUR provider lands.
- City/station name → ID resolution (RegioJet has a locations endpoint), likely
  as a second CLI tool the agent calls first.
```
