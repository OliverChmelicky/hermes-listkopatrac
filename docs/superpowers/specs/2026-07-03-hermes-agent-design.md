# Hermes Search Tool — Design

**Date:** 2026-07-03
**Status:** Approved (design), pending implementation plan

## Overview

Hermes is an LLM agent that the user sets up and runs themselves. It reads the
`skills/*.md` policy, talks to the user, asks for missing details, decides when
to search, and narrates results — **all of that lives in the agent, not in Go.**

This project builds **one tool the Hermes agent invokes: a Go CLI binary that
searches a travel provider (RegioJet) for connections A→B and returns ranked,
EUR-priced results as JSON on stdout.** The agent shells out to the binary and
narrates the JSON it gets back.

## Goals

- A single, dependency-free Go binary the agent calls with flags.
- Query a provider for connections A→B on a given day, honoring an optional
  "arrive by" deadline.
- Filter unavailable options, rank the rest by price in EUR, return the best N.
- Emit structured JSON (results + a small "how it searched" meta block) so the
  agent can both list options and describe the process.
- A description file in `tools/` so the Hermes agent knows how to call it.

## Non-goals (this project)

The following belong to the **Hermes agent**, not to this Go tool:

- **No LLM in Go.** No OpenRouter, no intake parsing, no clarifying questions,
  no result narration. The agent does all natural-language work.
- **No conversation/orchestration.** The binary is one-shot: flags in, JSON out.
- **No Telegram/CLI chat loop.** The agent owns the user channel.
- **No city→station-ID resolution.** The agent passes IDs (or omits them for
  defaults). Plain city names are not resolved here.
- **No real currency conversion.** RegioJet prices are already EUR; the
  converter is an identity seam until a non-EUR provider is added.
- **No booking.** Search and recommendation only.
- Only RegioJet. České dráhy and Leo Express are future providers.

## Architecture

A small Go program with a clear split:

- **`cmd/hermes-search`** — parses flags into a `SearchQuery`, runs the pipeline,
  prints JSON, sets an exit code.
- **`pkg/search`** — the pipeline: fan out over providers, normalize to EUR,
  rank, and assemble the `Output` (options + meta). Pure and testable.
- **`pkg/provider`** — a `Provider` interface and a concurrent registry, so
  adding the Nth provider is one new adapter.
- **`pkg/provider/regiojet`** — the one adapter, against the known REST endpoint.
- **`pkg/currency`**, **`pkg/rank`**, **`pkg/model`** — supporting units.

```
flags ──▶ SearchQuery ──▶ search.Run:
                             provider fan-out (concurrent)
                                 │
                                 ▼
                             currency → EUR (identity seam)
                                 │
                                 ▼
                             rank: filter + sort + take N
                                 │
                                 ▼
                             Output{options, meta} ──▶ JSON to stdout
```

### Package layout

```
cmd/hermes-search/main.go   flags → pipeline → JSON out
pkg/search/                 pipeline: fan-out + currency + rank + assemble Output
pkg/provider/               Provider interface + concurrent registry
  regiojet/                 RegioJet adapter
pkg/currency/               provider price → EUR (identity seam)
pkg/rank/                   filter + sort + take N (pure functions)
pkg/model/                  shared types
tools/                      hermes-search.md — tool description for the agent
```

## CLI contract

Binary: `hermes-search`

Flags:

| Flag          | Meaning                              | Default            |
|---------------|--------------------------------------|--------------------|
| `--from`      | from location ID                     | `10202001`         |
| `--from-type` | `CITY` or `STATION`                  | `CITY`             |
| `--to`        | to location ID                       | `372825000`        |
| `--to-type`   | `CITY` or `STATION`                  | `STATION`          |
| `--date`      | departure day `YYYY-MM-DD`           | **required**       |
| `--arrive-by` | RFC3339 deadline at destination      | none (optional)    |
| `--limit`     | max options to return                | `5`                |

Output: a single JSON object on stdout:

```json
{
  "options": [
    {
      "provider": "RegioJet",
      "departureTime": "2026-07-04T05:17:00+02:00",
      "arrivalTime": "2026-07-04T09:58:00+02:00",
      "priceFrom": 16.9,
      "priceTo": 29.9,
      "currency": "EUR",
      "freeSeats": 62,
      "transfers": 0,
      "travelTime": "04:41 h",
      "bookable": true,
      "priceEUR": 16.9
    }
  ],
  "meta": {
    "providersQueried": ["RegioJet"],
    "providerRaw": { "RegioJet": 18 },
    "rawCount": 18,
    "dropped": 3,
    "returned": 5
  }
}
```

Exit codes: `0` on success (even with zero options); non-zero with a message on
stderr for bad flags or a provider/transport error. Errors are plain text on
stderr so the agent can surface them.

## Core types

```go
type SearchQuery struct {
    FromLocationID   string
    FromLocationType string
    ToLocationID     string
    ToLocationType   string
    DepartureDate    time.Time  // day granularity
    ArriveBy         *time.Time // optional deadline at destination
    ResultCount      int
}

type Connection struct {
    Provider      string
    DepartureTime time.Time
    ArrivalTime   time.Time
    PriceFrom     float64
    PriceTo       float64
    Currency      string
    FreeSeats     int
    Transfers     int
    TravelTime    string
    Bookable      bool
}

type Option struct {
    Connection          // JSON: fields promoted
    PriceEUR   float64
}
```

`search.Output` (in `pkg/search`) wraps `[]Option` plus a `Meta` block
(`ProvidersQueried`, `ProviderRaw`, `RawCount`, `Dropped`, `Returned`).

## Pipeline flow (`search.Run`)

1. `provider.Registry.SearchAll` fans out over all registered providers
   **concurrently** (RegioJet only today; loop is N-ready) → `[]Connection` plus
   a per-provider raw count.
2. `currency.ToEURAll` → `[]Option` with `PriceEUR` (identity in v1).
3. `rank.Rank`: drop `!Bookable`, `FreeSeats == 0`, sold-out (`PriceFrom == 0`);
   drop anything arriving after `ArriveBy` when set; sort by `PriceEUR` asc; take
   `ResultCount`.
4. Assemble `Output{Options, Meta}`; `Meta.Dropped = rawCount - returned`.

The **"arrive by" filter is client-side** because RegioJet's `search/simple`
endpoint only accepts a departure *day*, not a target arrival time.

## RegioJet adapter

- **Endpoint:** `GET https://brn-ybus-pubapi.sa.cz/restapi/routes/search/simple`
- **Params:** `fromLocationId`, `fromLocationType`, `toLocationId`,
  `toLocationType`, `departureDate` (YYYY-MM-DD), `tariffs=REGULAR`,
  `fromLocationName=`, `toLocationName=` (empty).
- **Defaults:** `fromLocationId=10202001` (CITY), `toLocationId=372825000`
  (STATION) when the query leaves them empty.
- **Currency:** send header `X-Currency: EUR` so prices are deterministic.
- **Response mapping:** `routes[]` → `[]Connection`; times parsed from the
  offset format (`2006-01-02T15:04:05.000-07:00`). The adapter maps **every**
  route (including sold-out ones with `priceFrom: 0`); filtering is `rank`'s job.

## Tool description (`tools/hermes-search.md`)

A markdown file the Hermes agent reads to learn the tool: what it does, the
exact command line with an example, the flag meanings, and the JSON output
shape. This is how the agent decides to call the binary and how to parse it.

## Extensibility

- **Add a provider:** new package implementing the `Provider` interface, register
  it in the pipeline's registry. Fan-out picks it up with no other changes.
- **Add another tool for the agent:** a separate binary + its own `tools/*.md`
  description; independent of this one.

## Confirmed assumptions

1. Hermes (the agent) is set up and run by the user; this project delivers only
   the Go CLI search tool it calls.
2. The agent invokes the tool as a **CLI binary** (flags in, JSON out).
3. RegioJet prices are EUR; `currency.ToEUR` is an identity seam in v1.
4. City→station-ID resolution is out of scope; IDs are provided or default to
   the example.

## Future work

- Additional providers (České dráhy, Leo Express) via new adapters.
- Real currency conversion with an FX source when a non-EUR provider lands.
- City/station name → ID resolution (RegioJet has a locations endpoint), likely
  as a second CLI tool the agent calls first.
```
