"""
nlu/parser.py — Layer 1 of the chat architecture.

Responsibility: natural-language text → ParsedIntent.

This module has ZERO imports from services/ or routers/.
It only extracts intent and entities; it never executes queries.

Implemented in Issue #9.
"""

from __future__ import annotations

from models.chat_responses import ParsedIntent


def parse_query(text: str) -> ParsedIntent:
    """
    Parse a natural-language football question into a structured intent.

    Uses OpenAI gpt-4o-mini via function/tool calling.
    Falls back to intent="unknown" (never raises) if the API call fails
    or the response cannot be parsed.

    API key loaded from OPENAI_API_KEY environment variable.
    This function never hardcodes credentials.

    Examples
    --------
    "Top 5 wingers under 23 in the PL by assists"
    → ParsedIntent(intent="ranking", position="FWD", league="Premier League",
                   metric="assists", max_age=23, limit=5)

    "Compare Salah and Mbappe"
    → ParsedIntent(intent="comparison", players=["Salah", "Mbappe"])

    "Show me the best player"
    → ParsedIntent(intent="unknown")  # ambiguous — best at what?
    """
    # TODO (Issue #9)
    raise NotImplementedError("nlu.parser.parse_query — implement in Issue #9")
