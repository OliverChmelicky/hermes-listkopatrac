# Hermes Search Tool Implementation Plan (Python)

> **Status: implemented and tested.** The tool is built in Python 3 (stdlib
> only) because the machine has no Go toolchain. This document records the
> as-built structure; the source under `hermes_search/` and `tests/` is the
> source of truth.

**Goal:** A dependency-free Python CLI (`python -m hermes_search`) the Hermes agent invokes with flags to search RegioJet for A→B connections and get back ranked, EUR-priced results as JSON.

**Architecture:** `hermes_search.cli` parses flags into a `SearchQuery` and prints JSON. `hermes_search.search.run` runs the pipeline (concurrent provider fan-out → EUR normalization → filter/sort/take-N → assemble `{options, meta}`). Providers sit behind a protocol; RegioJet is the one adapter. No LLM, no conversation — the agent owns all natural-language work.

**Tech Stack:** Python 3.13, standard library only (`urllib`, `json`, `argparse`, `dataclasses`, `concurrent.futures`, `datetime`, `unittest`).

## Global Constraints

- **Standard library only** — no third-party dependencies (no pytest; tests use `unittest`).
- Package under `hermes_search/`; tests under `tests/`; tool description under `tools/`.
- Default `result_count` = 5. RegioJet defaults: `fromLocationId=10202001` (CITY), `toLocationId=372825000` (STATION).
- Currency is EUR throughout v1; `to_eur` is an identity seam.
- Options ranked ascending by `price_eur` (derived from `price_from`).
- One-shot: flags in, single JSON object out on stdout; plain-text errors on stderr. Exit `0` success, `2` bad flags, `1` search error.

## Tasks (as built)

Each unit was written test-first with `unittest` and verified with
`python -m unittest discover -s tests -t .` (15 tests, all passing).

### Task 1: Shared model types — `hermes_search/model.py`
- `SearchQuery`, `Connection`, `Option` dataclasses; `Default*` constants;
  `SearchQuery.with_defaults()`; `Option.to_json()` (flat camelCase dict).
- Tests: `tests/test_model.py` — defaults fill/keep, JSON shape.

### Task 2: Currency seam — `hermes_search/currency.py`
- `to_eur(Connection) -> Option` (identity, `price_eur = price_from`),
  `to_eur_all(conns) -> list[Option]`.
- Tests: `tests/test_currency.py`.

### Task 3: Ranking — `hermes_search/rank.py`
- `rank(options, query)`: drop unbookable / no-seats / sold-out (`price_from<=0`);
  drop arrivals after `arrive_by` when set; sort by `price_eur` asc; take
  `result_count`.
- Tests: `tests/test_rank.py` — filter+sort+limit, arrive-by.

### Task 4: Provider protocol + registry — `hermes_search/providers/base.py`
- `Provider` protocol (`name()`, `search(query)`), `Registry` with `register()`
  and `search_all(query) -> (connections, {name: raw_count})` using
  `ThreadPoolExecutor`. Provider errors propagate.
- Tests: `tests/test_registry.py` — aggregation/counts, error propagation.

### Task 5: RegioJet adapter — `hermes_search/providers/regiojet.py`
- `RegioJet` with `base_url`/`timeout`; `name()`, `search(query)`; builds the
  URL, sends `X-Currency: EUR`, maps every route (incl. sold-out) via
  `datetime.fromisoformat`.
- Tests: `tests/test_regiojet.py` — local `http.server` serving
  `tests/testdata/search_response.json`; asserts path, `X-Currency`,
  `departureDate`, sold-out mapping, sane times.

### Task 6: Search pipeline — `hermes_search/search.py`
- `run(registry, query) -> dict`: fan-out → `to_eur_all` → `rank` → assemble
  `{options: [...], meta: {providersQueried, providerRaw, rawCount, dropped, returned}}`.
- Tests: `tests/test_search.py` — ranking + meta counts.

### Task 7: CLI + tool description — `hermes_search/cli.py`, `hermes_search/__main__.py`, `hermes-search`, `tools/hermes-search.md`
- `build_parser()`, `build_query(args)`, `main(argv)`; flags per the contract;
  JSON to stdout; exit codes 0/2/1.
- Tests: `tests/test_cli.py` — flag parsing, defaults, arrive-by, bad-date error.
- Verified end-to-end against the live RegioJet API (24 routes → 3 cheapest EUR)
  and `--arrive-by` filtering.

## Verification performed

- `python -m unittest discover -s tests -t .` → 15 tests OK.
- `python -m hermes_search` (no `--date`) → exit 2 (argparse).
- `python -m hermes_search --date nope` → `error: ...` exit 2.
- `./hermes-search --date 2026-07-08 --limit 3` → JSON, 3 cheapest EUR options.
- `./hermes-search --date 2026-07-08 --arrive-by 2026-07-08T09:00:00+02:00` →
  only the 07:59 arrival kept.

## Future work

- Additional providers (České dráhy, Leo Express) via new adapter classes.
- Real currency conversion when a non-EUR provider is added.
- City/station name → ID resolution, likely as a second CLI tool.
