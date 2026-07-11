"""
services/chat_service.py — orchestration layer for POST /chat.

Architecture:
    ChatRequest.message
        ↓
    nlu.parse_query()      (Issue #9)
        ↓
    ParsedIntent
        ↓
    execute_chat_query()   ← this file
        ↓
    existing deterministic services (data, stats, comparison)
        ↓
    ChatResponse

This layer contains ZERO statistical logic.
All numbers come from existing services unchanged.
"""

from __future__ import annotations

import logging

from models.chat_responses import (
    ChatResponse,
    ChartDataset,
    ChartResponse,
    ComparisonResponse,
    TableResponse,
    TextResponse,
)
from models.player import PlayerSummary
from nlu.parser import parse_query
from services import comparison_service, data_service, stats_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MIN_MINUTES = 300
DEFAULT_LIMIT = 5
MAX_CLARIFICATION_CANDIDATES = 5

DEFAULT_UNKNOWN_MESSAGE = (
    "I'm not sure what you're asking. "
    "Try: 'Top 5 forwards in the Premier League by goals', "
    "'Show me Mohamed Salah', or 'Compare Salah and Kane'."
)
DEFAULT_ERROR_MESSAGE = (
    "I couldn't process that request. Please try rephrasing it."
)

# Human-readable label map for ranking table titles (supplement metric_label)
_METRIC_TITLE_LABEL: dict[str, str] = {
    "goals":         "Goals per 90",
    "assists":       "Assists per 90",
    "shots":         "Shots per 90",
    "passes":        "Passes per 90",
    "xg":            "xG per 90",
    "xa":            "xA per 90",
    "goals_p90":     "Goals per 90",
    "assists_p90":   "Assists per 90",
    "shots_p90":     "Shots per 90",
    "passes_p90":    "Passes per 90",
    "xg_p90":        "xG per 90",
    "xa_p90":        "xA per 90",
    "goals_per90":   "Goals per 90",
    "assists_per90": "Assists per 90",
    "shots_per90":   "Shots per 90",
    "passes_per90":  "Passes per 90",
    "xg_per90":      "xG per 90",
    "xa_per90":      "xA per 90",
    "goals_total":     "Goals (total)",
    "assists_total":   "Assists (total)",
    "shots_total":     "Shots (total)",
    "passes_total":    "Passes (total)",
    "xg_total":        "xG (total)",
    "xa_total":        "xA (total)",
    "minutes_played":  "Minutes played",
    "age":             "Age",
    "market_value_eur": "Market value (€)",
}

# Percentile metric order for radar charts
_RADAR_METRICS = [
    "goals_p90",
    "assists_p90",
    "shots_p90",
    "passes_p90",
    "xg_p90",
    "xa_p90",
]
_RADAR_LABELS = [
    "Goals",
    "Assists",
    "Shots",
    "Passes",
    "xG",
    "xA",
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def execute_chat_query(message: str) -> ChatResponse:
    """
    Parse the user message and dispatch to the correct service, returning
    a structured ChatResponse. Never raises — unexpected errors are caught
    and returned as a safe TextResponse.
    """
    try:
        intent = parse_query(message)

        if intent.intent == "ranking":
            return _handle_ranking(intent)
        if intent.intent == "player_lookup":
            return _handle_lookup(intent)
        if intent.intent == "comparison":
            return _handle_comparison(intent)

        # "unknown" or any future unhandled intent
        return _text(intent.clarification_message or DEFAULT_UNKNOWN_MESSAGE)

    except Exception:
        logger.exception("Unexpected error in execute_chat_query for message=%r", message)
        return _error(DEFAULT_ERROR_MESSAGE)


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------


def _handle_ranking(intent) -> ChatResponse:
    metric = intent.metric
    if not metric:
        return _text(
            "Which metric should I rank by, such as goals, assists or xG?"
        )

    position = intent.position
    league = intent.league
    limit = intent.limit or DEFAULT_LIMIT
    min_minutes = intent.min_minutes if intent.min_minutes is not None else DEFAULT_MIN_MINUTES

    try:
        ranked = stats_service.rank_players(
            metric,
            position=position,
            league=league,
            min_age=intent.min_age,
            max_age=intent.max_age,
            min_minutes=min_minutes,
            limit=limit,
        )
    except ValueError as exc:
        return _error(f"Unsupported metric: {exc}")

    if not ranked:
        return _error(
            "No players matched those filters. "
            "Try another league, position or minutes threshold."
        )

    metric_label = _METRIC_TITLE_LABEL.get(metric, metric)
    title_parts = [f"Top {len(ranked)}"]
    if league:
        title_parts.append(league)
    if position:
        title_parts.append(position)
    title_parts.append(f"by {metric_label}")
    title = " ".join(title_parts)

    columns = ["rank", "name", "club", "league", "position", "metric_value", "metric_label"]
    rows = [
        {
            "rank": p.rank,
            "name": p.name,
            "club": p.club,
            "league": p.league,
            "position": p.position,
            "metric_value": p.metric_value,
            "metric_label": p.metric_label,
        }
        for p in ranked
    ]

    return ChatResponse(
        response=TableResponse(title=title, columns=columns, rows=rows)
    )


def _handle_lookup(intent) -> ChatResponse:
    players = intent.players
    if not players:
        return _text("Which specific player are you asking about?")

    name = players[0]
    resolved = resolve_player_name(name)
    if isinstance(resolved, ChatResponse):
        return resolved

    profile = stats_service.get_player_profile_stats(resolved.player_id)
    if profile is None:
        return _error(f'Player "{name}" was found but their stats are unavailable.')

    # Build radar chart from percentiles
    if profile.percentiles and profile.percentiles.metrics:
        labels: list[str] = []
        data: list[float] = []
        for metric_key, label in zip(_RADAR_METRICS, _RADAR_LABELS):
            val = profile.percentiles.metrics.get(metric_key)
            if val is not None:
                labels.append(label)
                data.append(val)

        if labels:
            peer_avg = [50.0] * len(labels)
            return ChatResponse(
                response=ChartResponse(
                    title=f"{profile.name} vs {profile.position} peers in {profile.league}",
                    chart_type="radar",
                    labels=labels,
                    datasets=[
                        ChartDataset(label=profile.name, data=data),
                        ChartDataset(label="Peer average", data=peer_avg),
                    ],
                )
            )

    # Fallback: text summary with deterministic fields
    mv = f"€{profile.market_value_eur:,}" if profile.market_value_eur else "N/A"
    summary = (
        f"{profile.name} — {profile.position}, {profile.club} ({profile.league})\n"
        f"Age: {profile.age} | Goals: {profile.goals} | Assists: {profile.assists} | "
        f"Minutes: {profile.minutes_played} | Market value: {mv}"
    )
    return _text(summary)


def _handle_comparison(intent) -> ChatResponse:
    players = intent.players
    if len(players) < 2:
        return _text("Please provide two player names to compare.")

    resolved_a = resolve_player_name(players[0])
    if isinstance(resolved_a, ChatResponse):
        return resolved_a

    resolved_b = resolve_player_name(players[1])
    if isinstance(resolved_b, ChatResponse):
        return resolved_b

    result = comparison_service.compare_players(
        resolved_a.player_id, resolved_b.player_id
    )
    if result is None:
        return _error(
            f"Could not compare {players[0]} and {players[1]}. "
            "One or both players may have insufficient data."
        )

    return ChatResponse(response=ComparisonResponse(result=result))


# ---------------------------------------------------------------------------
# Player-name resolver
# ---------------------------------------------------------------------------


def resolve_player_name(name: str) -> PlayerSummary | ChatResponse:
    """
    Resolve a player name string to a single PlayerSummary.

    Returns a ChatResponse (TextResponse) if resolution fails or is ambiguous.
    """
    matches = data_service.search_players(name)

    if not matches:
        return _error(f'I couldn\'t find a player matching "{name}".')

    if len(matches) == 1:
        return matches[0]

    # Check for a case-insensitive exact full-name match among candidates
    exact = [m for m in matches if m.name.lower() == name.lower()]
    if len(exact) == 1:
        return exact[0]

    # Ambiguous — list up to five candidates
    candidates = ", ".join(m.name for m in matches[:MAX_CLARIFICATION_CANDIDATES])
    return _text(
        f'I found multiple players matching "{name}": {candidates}. '
        "Please use the full player name."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text(message: str) -> ChatResponse:
    return ChatResponse(response=TextResponse(message=message, is_error=False))


def _error(message: str) -> ChatResponse:
    return ChatResponse(response=TextResponse(message=message, is_error=True))
