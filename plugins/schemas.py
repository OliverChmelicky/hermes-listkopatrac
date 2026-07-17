"""Tool schemas — what the LLM sees."""

SEARCH_CONNECTIONS = {
    "name": "search_connections",
    "description": (
        "Search RegioJet for train/bus connections between two locations on a "
        "given day and return options ranked cheapest-first in EUR. Use this "
        "when the user asks for connections, prices, seat availability, or the "
        "cheapest way to travel between two places. Sold-out and unbookable "
        "routes are excluded. The tool does NOT resolve city names to IDs and "
        "does NOT ask follow-up questions: gather any missing detail (especially "
        "the date) from the user first, then call it. Pass RegioJet numeric "
        "location IDs, or omit them to use the Olomouc→Prague defaults. The JSON "
        "result also includes a 'meta' block describing how the search was run "
        "so you can explain the process to the user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Departure day, YYYY-MM-DD (required).",
            },
            "from_location_id": {
                "type": "string",
                "description": "RegioJet from-location ID. Default 10202001 (Olomouc, CITY).",
            },
            "from_location_type": {
                "type": "string",
                "enum": ["CITY", "STATION"],
                "description": "Type of the from-location. Default CITY.",
            },
            "to_location_id": {
                "type": "string",
                "description": "RegioJet to-location ID. Default 372825000 (Prague, STATION).",
            },
            "to_location_type": {
                "type": "string",
                "enum": ["CITY", "STATION"],
                "description": "Type of the to-location. Default STATION.",
            },
            "arrive_by": {
                "type": "string",
                "description": (
                    "Optional latest arrival time at the destination, ISO 8601 "
                    "WITH UTC offset, e.g. '2026-07-08T18:00:00+02:00'. Options "
                    "arriving later are excluded."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of options to return. Default 5.",
            },
        },
        "required": ["date"],
    },
}
