"""Hermes search tool.

A small, dependency-free CLI the Hermes agent invokes to search travel
providers (RegioJet today) for connections A -> B on a given day. It filters,
ranks by price in EUR, and prints JSON on stdout. All natural-language work
(understanding the request, asking for missing details, narrating results)
lives in the agent, not here.
"""
