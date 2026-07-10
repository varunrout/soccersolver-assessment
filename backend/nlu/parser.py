"""
nlu/parser.py — Layer 1 of the chat architecture.

Responsibility: natural-language text → ParsedIntent.

This module has ZERO imports from services/ or routers/.
It only extracts intent and entities; it never executes queries.

Strategy:
  1. Deterministic preprocessing and validation.
  2. OpenAI structured tool calling when OPENAI_API_KEY is set.
  3. Rule-based fallback when no key is set or OpenAI call fails.

Environment variables:
  OPENAI_API_KEY  — optional; enables LLM path
  OPENAI_MODEL    — optional; default "gpt-4o-mini"

Implemented in Issue #9.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from models.chat_responses import ParsedIntent

# OpenAI is imported at module level so tests can patch 'nlu.parser.OpenAI'.
# The import is guarded: if the package is missing the LLM path simply never runs.
try:
    from openai import OpenAI as OpenAI  # noqa: PLC0414
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_LIMIT = 50
MIN_LIMIT = 1

# ---------------------------------------------------------------------------
# Normalisation tables
# ---------------------------------------------------------------------------

# Sorted longest-first so longer phrases are matched before shorter substrings.
_LEAGUE_ALIASES: list[tuple[str, str]] = sorted(
    [
        ("premier league", "Premier League"),
        ("english premier league", "Premier League"),
        ("epl", "Premier League"),
        ("pl", "Premier League"),
        ("la liga", "La Liga"),
        ("laliga", "La Liga"),
        ("spanish league", "La Liga"),
        ("serie a", "Serie A"),
        ("seriea", "Serie A"),
        ("italian league", "Serie A"),
        ("bundesliga", "Bundesliga"),
        ("german league", "Bundesliga"),
        ("ligue 1", "Ligue 1"),
        ("ligue1", "Ligue 1"),
        ("french league", "Ligue 1"),
    ],
    key=lambda t: -len(t[0]),
)

_POSITION_ALIASES: list[tuple[str, str]] = sorted(
    [
        ("centre-back", "DEF"),
        ("center-back", "DEF"),
        ("centreback", "DEF"),
        ("centerback", "DEF"),
        ("full-back", "DEF"),
        ("fullback", "DEF"),
        ("goalkeeper", "GK"),
        ("goalkeepers", "GK"),
        ("midfielders", "MID"),
        ("midfielder", "MID"),
        ("midfield", "MID"),
        ("defenders", "DEF"),
        ("defender", "DEF"),
        ("attackers", "FWD"),
        ("attacker", "FWD"),
        ("forwards", "FWD"),
        ("forward", "FWD"),
        ("strikers", "FWD"),
        ("striker", "FWD"),
        ("wingers", "FWD"),
        ("winger", "FWD"),
        ("keepers", "GK"),
        ("keeper", "GK"),
        ("goalie", "GK"),
    ],
    key=lambda t: -len(t[0]),
)

# Metric aliases — longer phrases first so "total goals" matches before "goals".
_METRIC_ALIASES: list[tuple[str, str]] = [
    ("expected goals per 90", "xg_p90"),
    ("expected assists per 90", "xa_p90"),
    ("goals per 90",           "goals_p90"),
    ("goals per game",         "goals_p90"),
    ("assists per 90",         "assists_p90"),
    ("assists per game",       "assists_p90"),
    ("shots per 90",           "shots_p90"),
    ("passes per 90",          "passes_p90"),
    ("xg per 90",              "xg_p90"),
    ("xa per 90",              "xa_p90"),
    ("total goals",            "goals_total"),
    ("goals total",            "goals_total"),
    ("season goals",           "goals_total"),
    ("overall goals",          "goals_total"),
    ("total assists",          "assists_total"),
    ("assists total",          "assists_total"),
    ("season assists",         "assists_total"),
    ("overall assists",        "assists_total"),
    ("total shots",            "shots_total"),
    ("total passes",           "passes_total"),
    ("market value",           "market_value_eur"),
    ("transfer value",         "market_value_eur"),
    ("minutes played",         "minutes_played"),
    ("playing time",           "minutes_played"),
    ("expected goals",         "xg"),
    ("expected assists",       "xa"),
    ("goals",                  "goals"),
    ("goal",                   "goals"),
    ("assists",                "assists"),
    ("assist",                 "assists"),
    ("shots",                  "shots"),
    ("shot",                   "shots"),
    ("passes",                 "passes"),
    ("xg",                     "xg"),
    ("xa",                     "xa"),
    ("minutes",                "minutes_played"),
]

# Words that are never a real player name on their own
_VAGUE_WORDS = frozenset({
    "best", "top", "worst", "better", "greatest", "good", "great",
    "player", "players", "footballer", "footballers", "anyone",
    "someone", "football", "soccer", "sport", "game", "season",
})

_STOP_WORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "of", "for", "to", "is", "are",
    "was", "me", "my", "his", "her", "their", "its", "this", "that",
    "by", "with", "from", "as", "be", "who",
})

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _normalize_league(text: str) -> str | None:
    low = text.lower()
    for alias, canonical in _LEAGUE_ALIASES:
        if re.search(r'\b' + re.escape(alias) + r'\b', low):
            return canonical
    return None


def _normalize_position(low: str) -> str | None:
    for alias, code in _POSITION_ALIASES:
        if re.search(r'\b' + re.escape(alias) + r'\b', low):
            return code
    return None


def _normalize_metric(candidate: str) -> str | None:
    low = candidate.strip().lower()
    for alias, normalized in _METRIC_ALIASES:
        if low == alias:
            return normalized
    # substring fallback for multi-word phrases captured in context
    for alias, normalized in _METRIC_ALIASES:
        if alias in low:
            return normalized
    return None


def _extract_metric(low: str) -> str | None:
    # Context-aware: look after "by" first (most reliable signal).
    # Capture up to end-of-string OR until a stop-preposition begins.
    by_m = re.search(
        r'\bby\s+([\w\s/]+?)(?:\s*$|\s+(?:in|from|for|under|over|with|who|at)\b)',
        low,
    )
    if by_m:
        m = _normalize_metric(by_m.group(1).strip())
        if m:
            return m
    # Then scan for any metric alias in the text (longer phrases first)
    for alias, normalized in _METRIC_ALIASES:
        if re.search(r'\b' + re.escape(alias) + r'\b', low):
            return normalized
    return None


def _extract_limit(low: str) -> int | None:
    m = re.search(r'\b(?:top|best)\s+(\d+)\b', low)
    if not m:
        m = re.search(r'\b(\d+)\s+(?:top|best|highest|leading)\b', low)
    if m:
        return max(MIN_LIMIT, min(MAX_LIMIT, int(m.group(1))))
    return None


def _extract_ages(low: str) -> tuple[int | None, int | None]:
    min_age: int | None = None
    max_age: int | None = None

    over_m = re.search(
        r'\b(?:over|older\s+than|aged?\s+(?:at\s+least|over))\s+(\d+)\b', low
    )
    if over_m:
        val = int(over_m.group(1))
        min_age = val if val > 0 else None

    under_m = re.search(
        r'\b(?:under|younger\s+than|aged?\s+(?:under|below|at\s+most))\s+(\d+)\b', low
    )
    if under_m:
        val = int(under_m.group(1))
        max_age = val if val > 0 else None

    return min_age, max_age


def _clean_name(text: str) -> str:
    text = text.strip().strip(".,?!")
    return " ".join(
        w for w in text.split() if w.lower() not in _STOP_WORDS
    ).strip()


def _looks_like_player_name(original_text: str, candidate: str) -> bool:
    """
    Heuristic: a real player name should appear with at least one
    capitalized word in the original text (not just sentence-start).
    Returns False when the candidate is only vague query words.
    """
    if not candidate:
        return False
    words = candidate.lower().split()
    if all(w in _VAGUE_WORDS for w in words):
        return False
    # Find the candidate in the original text (case-insensitive)
    m = re.search(re.escape(candidate), original_text, re.I)
    if not m:
        # Candidate might be cleaned (stop words stripped); accept if it
        # wasn't all vague words (already checked above).
        return True
    matched = original_text[m.start(): m.end()].split()
    query_words = original_text.split()
    first_word = query_words[0] if query_words else ""
    return any(
        w[0].isupper() and w.lower() not in _STOP_WORDS and w != first_word
        for w in matched
    )


# ---------------------------------------------------------------------------
# Intent-detection patterns
# ---------------------------------------------------------------------------

_COMP_PATTERNS: list[tuple[re.Pattern, tuple[int, int]]] = [
    (re.compile(r'\bcompare\s+(.+?)\s+and\s+(.+?)(?:\s*[?.,]?\s*$)', re.I | re.DOTALL), (1, 2)),
    (re.compile(r'^(.+?)\s+vs\.?\s+(.+?)(?:\s*[?.,]?\s*$)', re.I | re.DOTALL), (1, 2)),
    (re.compile(r'^(.+?)\s+versus\s+(.+?)(?:\s*[?.,]?\s*$)', re.I | re.DOTALL), (1, 2)),
    (re.compile(r'\bwho\s+is\s+better[,\s]+(.+?)\s+or\s+(.+?)(?:\s*[?.,]?\s*$)', re.I | re.DOTALL), (1, 2)),
    (re.compile(r'\bis\s+(.+?)\s+better\s+than\s+(.+?)(?:\s*[?.,]?\s*$)', re.I | re.DOTALL), (1, 2)),
]

_RANK_PATTERNS: list[re.Pattern] = [
    re.compile(r'\btop\s+\d+\b', re.I),
    re.compile(r'\bbest\s+\d+\b', re.I),
    re.compile(
        r'\b(?:top|best)\s+(?:forward|midfielder|defender|goalkeeper|striker|'
        r'winger|attacker|keeper|player)s?\b', re.I
    ),
    re.compile(
        r'\b(?:top|best)\s+\w+s?\s+(?:in|by|from|of)\b', re.I
    ),
    re.compile(r'\b(?:highest|most)\s+(?:goals|assists|shots|passes|xg|xa)\b', re.I),
    re.compile(r'\b(?:rank|ranking|ranked)\b', re.I),
    re.compile(r'\bby\s+(?:goals|assists|shots|passes|xg|xa|market\s+value|minutes)\b', re.I),
]

_LOOKUP_TRIGGERS: list[re.Pattern] = [
    re.compile(r'\bshow\s+me\b', re.I),
    re.compile(r'\btell\s+me\s+about\b', re.I),
    re.compile(r'\bwho\s+is\b', re.I),
    re.compile(r'\bhow\s+(?:is|does)\b', re.I),
    re.compile(r'\bprofile\s+(?:of|for)?\b', re.I),
    re.compile(r'\bstats?\s+(?:of|for)\b', re.I),
    re.compile(r'\baverage\s+(?:forward|midfielder|defender|goalkeeper|striker|winger)\b', re.I),
]

_LOOKUP_EXTRACT: list[re.Pattern] = [
    re.compile(r'\bshow\s+me\s+(.+?)(?:\s*[?.,]|$)', re.I),
    re.compile(r'\btell\s+me\s+about\s+(.+?)(?:\s*[?.,]|$)', re.I),
    re.compile(r'\bwho\s+is\s+(.+?)(?:\s*[?.,]|$)', re.I),
    re.compile(r'\bhow\s+(?:is|does)\s+(.+?)\s+(?:compare|perform|play|doing)\b', re.I),
    re.compile(r'\bstats?\s+(?:of|for)\s+(.+?)(?:\s*[?.,]|$)', re.I),
    re.compile(r'\bprofile\s+(?:of|for)?\s*(.+?)(?:\s*[?.,]|$)', re.I),
]


def _is_comparison(text: str) -> bool:
    low = text.lower()
    if re.search(r'\bvs\.?\b|\bversus\b', low):
        return True
    if re.search(r'\bcompare\b', low):
        # "compare to the average X" is a player-profile query, not two-player comparison
        if not re.search(r'\bcompare\s+to\s+the\s+average\b', low):
            return True
    if re.search(r'\bwho\s+is\s+better\b|\bis\s+\S+\s+better\s+than\b', low):
        return True
    return False


def _is_ranking(low: str) -> bool:
    return any(p.search(low) for p in _RANK_PATTERNS)


def _is_lookup(low: str) -> bool:
    return any(p.search(low) for p in _LOOKUP_TRIGGERS)


def _extract_comparison_players(text: str) -> list[str] | None:
    for pattern, (g1, g2) in _COMP_PATTERNS:
        m = pattern.search(text)
        if m:
            name_a = _clean_name(m.group(g1))
            name_b = _clean_name(m.group(g2))
            if name_a and name_b:
                return [name_a, name_b]
    return None


def _extract_lookup_player(text: str) -> list[str]:
    for pattern in _LOOKUP_EXTRACT:
        m = pattern.search(text)
        if m:
            candidate = _clean_name(m.group(1))
            if candidate and _looks_like_player_name(text, candidate):
                return [candidate]
    return []


# ---------------------------------------------------------------------------
# Rule-based parser
# ---------------------------------------------------------------------------


def _parse_rule_based(text: str) -> ParsedIntent:
    low = text.lower()
    league   = _normalize_league(text)
    position = _normalize_position(low)
    metric   = _extract_metric(low)
    limit    = _extract_limit(low)
    min_age, max_age = _extract_ages(low)

    if _is_comparison(text):
        players = _extract_comparison_players(text)
        if players and len(players) == 2:
            return ParsedIntent(
                intent="comparison",
                players=players,
                league=league,
                metric=metric,
                raw_query=text,
            )
        return ParsedIntent(
            intent="unknown",
            clarification_message="Please provide two player names to compare.",
            raw_query=text,
        )

    if _is_ranking(low):
        if not metric:
            return ParsedIntent(
                intent="unknown",
                position=position,
                league=league,
                limit=limit,
                min_age=min_age,
                max_age=max_age,
                clarification_message="Which metric should I rank by, such as goals, assists or xG?",
                raw_query=text,
            )
        return ParsedIntent(
            intent="ranking",
            metric=metric,
            position=position,
            league=league,
            limit=limit,
            min_age=min_age,
            max_age=max_age,
            raw_query=text,
        )

    if _is_lookup(low):
        players = _extract_lookup_player(text)
        if players:
            return ParsedIntent(
                intent="player_lookup",
                players=players,
                league=league,
                position=position,
                raw_query=text,
            )
        # Lookup trigger but no recognisable player name → unknown
        return ParsedIntent(
            intent="unknown",
            clarification_message="Which specific player are you asking about?",
            raw_query=text,
        )

    return ParsedIntent(
        intent="unknown",
        clarification_message=(
            "I'm not sure what you're asking. "
            "Try: 'Top 5 forwards in the Premier League by goals' "
            "or 'Compare Salah and Kane'."
        ),
        raw_query=text,
    )


# ---------------------------------------------------------------------------
# Optional OpenAI integration
# ---------------------------------------------------------------------------

_OPENAI_SYSTEM_PROMPT = (
    "You are a football analytics assistant. "
    "Extract structured intent from user queries using the provided tool.\n\n"
    "Rules:\n"
    "- intent: 'ranking' for top-N queries, 'comparison' for two specific players,\n"
    "  'player_lookup' for one player or player-vs-average, 'unknown' for anything else.\n"
    "- players: exact names from the query only. Do NOT invent names.\n"
    "- position: normalize to FWD, MID, DEF, GK or null.\n"
    "- league: normalize to 'Premier League', 'La Liga', 'Serie A', 'Bundesliga',\n"
    "  'Ligue 1', or null.\n"
    "- metric: use: goals, assists, shots, passes, xg, xa, goals_p90, assists_p90,\n"
    "  xg_p90, xa_p90, goals_total, assists_total, market_value_eur, minutes_played.\n"
    "  Default to per-90 (e.g. goals) unless 'total' is explicitly stated.\n"
    "- limit: number requested (1-50) or null.\n"
    "- Never calculate statistics. Never invent player names."
)

_PARSE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "extract_football_intent",
        "description": "Extract structured intent and entities from a football analytics query.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["ranking", "player_lookup", "comparison", "unknown"],
                },
                "players":     {"type": "array", "items": {"type": "string"}},
                "metric":      {"type": ["string", "null"]},
                "position":    {"type": ["string", "null"], "enum": ["FWD", "MID", "DEF", "GK", None]},
                "league":      {"type": ["string", "null"]},
                "min_age":     {"type": ["integer", "null"]},
                "max_age":     {"type": ["integer", "null"]},
                "min_minutes": {"type": ["integer", "null"]},
                "limit":       {"type": ["integer", "null"]},
                "clarification_message": {"type": ["string", "null"]},
            },
            "required": ["intent"],
        },
    },
}


def _parse_with_openai(text: str) -> ParsedIntent | None:
    """
    Try to parse the query with OpenAI tool calling.
    Returns None when:
      - OPENAI_API_KEY is not set
      - OpenAI package is unavailable
      - the API call fails for any reason
      - the response cannot be validated as ParsedIntent

    Never raises.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None

    try:
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": _OPENAI_SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ],
            tools=[_PARSE_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_football_intent"}},
            temperature=0,
        )

        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            return None

        raw: dict[str, Any] = json.loads(tool_calls[0].function.arguments)

        # Sanitise before constructing the model
        if raw.get("limit") is not None:
            raw["limit"] = max(MIN_LIMIT, min(MAX_LIMIT, int(raw["limit"])))
        for age_field in ("min_age", "max_age"):
            if raw.get(age_field) is not None and int(raw[age_field]) < 0:
                raw[age_field] = None
        raw.setdefault("raw_query", text)
        raw.setdefault("players", [])

        return ParsedIntent(**raw)

    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI parse failed (%s); falling back to rule-based parser.", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_query(text: str) -> ParsedIntent:
    """
    Parse a natural-language football question into a structured ParsedIntent.

    1. Trims input; blank → intent="unknown" with a helpful message.
    2. Tries OpenAI if OPENAI_API_KEY is set.
    3. Falls back to deterministic rule-based parser.

    Never raises to the caller.
    """
    text = (text or "").strip()

    if not text:
        return ParsedIntent(
            intent="unknown",
            clarification_message=(
                "Please ask a football question, such as "
                "'Top 5 forwards in the Premier League by goals'."
            ),
            raw_query="",
        )

    try:
        result = _parse_with_openai(text)
        if result is not None:
            return result
        return _parse_rule_based(text)
    except Exception as exc:  # noqa: BLE001
        logger.error("parse_query failed unexpectedly: %s", exc)
        return ParsedIntent(
            intent="unknown",
            clarification_message="Something went wrong. Please try again.",
            raw_query=text,
        )

