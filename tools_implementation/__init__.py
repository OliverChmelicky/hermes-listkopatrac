"""Hermes search plugin — registration.

Provides one tool, ``search_connections``, backed by the ``hermes_search``
engine subpackage. Wires the schema (what the LLM reads) to the handler (the
code that runs) via ``register(ctx)``.
"""

import logging

from . import schemas, tools

logger = logging.getLogger(__name__)


def register(ctx):
    """Wire schemas to handlers."""
    ctx.register_tool(
        name="search_connections",
        toolset="hermes_search",
        schema=schemas.SEARCH_CONNECTIONS,
        handler=tools.search_connections,
    )
    logger.debug("Registered hermes_search plugin (tool: search_connections)")
