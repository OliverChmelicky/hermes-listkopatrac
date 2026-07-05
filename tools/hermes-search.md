# hermes-search

Searches RegioJet for train/bus connections between two locations on a given day
and returns ranked, EUR-priced options as JSON on stdout. Use this tool when the
user asks for connections, prices, or availability between two places.

## Command

    python -m hermes_search --date YYYY-MM-DD [options]

(or `./hermes-search --date YYYY-MM-DD [options]` from the repo root)

## Flags

- `--date` (required): departure day, `YYYY-MM-DD`.
- `--from` / `--to`: location IDs. Default `10202001` (CITY) -> `372825000` (STATION).
- `--from-type` / `--to-type`: `CITY` or `STATION`. Default `CITY` / `STATION`.
- `--arrive-by` (optional): keep only options arriving at or before this time at
  the destination. ISO 8601 **with UTC offset**, e.g. `2026-07-08T18:00:00+02:00`.
- `--limit` (optional): max options to return. Default `5`.

## Example

    python -m hermes_search --date 2026-07-08 --from 10202001 --to 372825000 --limit 3

## Output

A single JSON object on stdout. `options` is sorted cheapest-first in EUR;
sold-out and unbookable routes are excluded. `meta` describes how the search ran
so you can explain it to the user.

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

## Exit codes

- `0`: success (even if `options` is empty).
- `2`: bad or missing flags (e.g. missing `--date`, malformed date).
- `1`: search or network error (message on stderr).

## Notes

- Prices are already in EUR. `priceFrom` is the cheapest fare; ranking uses it.
- The tool does not resolve city names to IDs. Pass RegioJet location IDs, or
  omit `--from`/`--to` to use the Olomouc -> Prague defaults.
- The tool is one-shot and stateless: it does not ask follow-up questions. If the
  request is missing details (like the date), ask the user yourself before calling.
