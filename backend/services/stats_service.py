"""
stats_service.py — deterministic per-90 metrics, percentiles, and rankings.

All player data comes exclusively from data_service.
No CSV reads, no LLM calls, no comparison logic.

Implemented in Issue #6.
"""

from __future__ import annotations

from typing import Any

from models.player import PlayerDetail, PlayerDetailWithPercentiles, PlayerPercentiles, RankedPlayer
from services.data_service import get_player_by_id, get_players

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_PEER_GROUP_SIZE = 5
DEFAULT_MIN_MINUTES = 300
MAX_RANK_LIMIT = 50
P90_ROUND = 3  # decimal places for per-90 values

# Metric registry ─ keys are the canonical names accepted by public functions.
# Value: (raw_column, human_label, is_per90)
_METRIC_REGISTRY: dict[str, tuple[str, str, bool]] = {
    # canonical per-90 names  (_p90 suffix)
    "goals_p90":   ("goals",   "Goals per 90",   True),
    "assists_p90": ("assists", "Assists per 90",  True),
    "shots_p90":   ("shots",   "Shots per 90",    True),
    "passes_p90":  ("passes",  "Passes per 90",   True),
    "xg_p90":      ("xg",      "xG per 90",       True),
    "xa_p90":      ("xa",      "xA per 90",       True),
    # _per90 aliases — identical to _p90 equivalents
    "goals_per90":   ("goals",   "Goals per 90",   True),
    "assists_per90": ("assists", "Assists per 90",  True),
    "shots_per90":   ("shots",   "Shots per 90",    True),
    "passes_per90":  ("passes",  "Passes per 90",   True),
    "xg_per90":      ("xg",      "xG per 90",       True),
    "xa_per90":      ("xa",      "xA per 90",       True),
    # short names — treated as per-90 for ranking (same order as _p90)
    "goals":   ("goals",   "Goals per 90",   True),
    "assists": ("assists", "Assists per 90",  True),
    "shots":   ("shots",   "Shots per 90",    True),
    "passes":  ("passes",  "Passes per 90",   True),
    "xg":      ("xg",      "xG per 90",       True),
    "xa":      ("xa",      "xA per 90",       True),
    # explicit raw season-total aliases
    "goals_total":   ("goals",   "Goals",           False),
    "assists_total": ("assists", "Assists",          False),
    "shots_total":   ("shots",   "Shots",            False),
    "passes_total":  ("passes",  "Passes",           False),
    "xg_total":      ("xg",      "xG",              False),
    "xa_total":      ("xa",      "xA",              False),
    # always-raw fields
    "minutes_played":    ("minutes_played",    "Minutes played",   False),
    "age":               ("age",               "Age",              False),
    "market_value_eur":  ("market_value_eur",  "Market value (€)", False),
}

SUPPORTED_METRICS: frozenset[str] = frozenset(_METRIC_REGISTRY)

# The per-90 metrics that appear in PlayerPercentiles.metrics
_PERCENTILE_METRICS: list[str] = [
    "goals_p90", "assists_p90", "shots_p90", "passes_p90", "xg_p90", "xa_p90"
]

# ---------------------------------------------------------------------------
# Internal per-90 helpers
# ---------------------------------------------------------------------------


def _per90(raw_value: float, minutes_played: int) -> float | None:
    """Return raw_value normalised per 90 minutes, or None if minutes <= 0."""
    if minutes_played <= 0:
        return None
    return round(raw_value / minutes_played * 90, P90_ROUND)


def _player_per90_values(player: PlayerDetail) -> dict[str, float | None]:
    """Return all per-90 values for a player keyed by metric name."""
    mp = player.minutes_played
    return {
        "goals_p90":   _per90(player.goals,   mp),
        "assists_p90": _per90(player.assists,  mp),
        "shots_p90":   _per90(player.shots,    mp),
        "passes_p90":  _per90(player.passes,   mp),
        "xg_p90":      _per90(player.xg,       mp),
        "xa_p90":      _per90(player.xa,       mp),
    }


def _get_metric_value(player: PlayerDetail, metric: str) -> float | None:
    """
    Return a player's value for the requested metric.

    For per-90 metrics, applies normalisation.
    For raw metrics, returns the column value directly.
    Raises ValueError for unknown metrics.
    """
    if metric not in _METRIC_REGISTRY:
        supported = ", ".join(sorted(SUPPORTED_METRICS))
        raise ValueError(
            f"Unknown metric '{metric}'. Supported metrics: {supported}"
        )
    col, _label, is_per90 = _METRIC_REGISTRY[metric]
    raw: Any = getattr(player, col)
    if is_per90:
        return _per90(float(raw), player.minutes_played)
    return float(raw)


# ---------------------------------------------------------------------------
# Peer group
# ---------------------------------------------------------------------------


def get_peer_group(
    position: str,
    league: str,
    min_minutes: int = DEFAULT_MIN_MINUTES,
) -> list[PlayerDetail]:
    """
    Return all players in the same position + league with sufficient minutes.

    Position and league comparisons are case-insensitive.
    """
    return get_players(
        position=position,
        league=league,
        min_minutes=max(1, min_minutes),  # always exclude zero-minute players
    )


# ---------------------------------------------------------------------------
# Percentiles
# ---------------------------------------------------------------------------


def _compute_percentile(player_value: float, peer_values: list[float]) -> float:
    """
    Deterministic percentile rank using inclusive count.

    percentile = 100 * count(v <= player_value) / len(peer_values)
    Range: 0.0 – 100.0, rounded to 1 decimal place.
    """
    count_le = sum(1 for v in peer_values if v <= player_value)
    return round(100.0 * count_le / len(peer_values), 1)


def get_player_percentiles(player_id: str) -> PlayerPercentiles | None:
    """
    Compute per-90 percentile ranks for a player vs their position+league peer group.

    Returns None when:
    - player_id is not found
    - player has zero minutes_played
    - peer group has fewer than MIN_PEER_GROUP_SIZE players

    Metrics returned: goals_p90, assists_p90, shots_p90, passes_p90, xg_p90, xa_p90
    Each value is 0–100 or None when peer group is too small.
    """
    player = get_player_by_id(player_id)
    if player is None or player.minutes_played <= 0:
        return None

    peers = get_peer_group(player.position, player.league)
    if len(peers) < MIN_PEER_GROUP_SIZE:
        return PlayerPercentiles(
            player_id=player_id,
            metrics={m: None for m in _PERCENTILE_METRICS},
        )

    player_p90 = _player_per90_values(player)
    result_metrics: dict[str, float | None] = {}

    for metric_key in _PERCENTILE_METRICS:
        player_val = player_p90[metric_key]
        if player_val is None:
            result_metrics[metric_key] = None
            continue

        peer_vals: list[float] = []
        for p in peers:
            v = _per90(getattr(p, _METRIC_REGISTRY[metric_key][0]), p.minutes_played)
            if v is not None:
                peer_vals.append(v)

        if len(peer_vals) < MIN_PEER_GROUP_SIZE:
            result_metrics[metric_key] = None
        else:
            result_metrics[metric_key] = _compute_percentile(player_val, peer_vals)

    return PlayerPercentiles(player_id=player_id, metrics=result_metrics)


# ---------------------------------------------------------------------------
# League averages
# ---------------------------------------------------------------------------


def get_league_averages(
    position: str,
    league: str,
    min_minutes: int = DEFAULT_MIN_MINUTES,
) -> dict[str, float]:
    """
    Return mean per-90 values for each metric within a position+league peer group.

    Keys: goals_p90, assists_p90, shots_p90, passes_p90, xg_p90, xa_p90
    Players with zero minutes are excluded.
    Returns zeros for all metrics if peer group is empty.
    """
    peers = get_peer_group(position, league, min_minutes=min_minutes)
    if not peers:
        return {m: 0.0 for m in _PERCENTILE_METRICS}

    sums: dict[str, float] = {m: 0.0 for m in _PERCENTILE_METRICS}
    counts: dict[str, int] = {m: 0 for m in _PERCENTILE_METRICS}

    for p in peers:
        p90 = _player_per90_values(p)
        for key in _PERCENTILE_METRICS:
            v = p90[key]
            if v is not None:
                sums[key] += v
                counts[key] += 1

    return {
        key: round(sums[key] / counts[key], P90_ROUND) if counts[key] else 0.0
        for key in _PERCENTILE_METRICS
    }


# ---------------------------------------------------------------------------
# Profile stats
# ---------------------------------------------------------------------------


def get_player_profile_stats(player_id: str) -> PlayerDetailWithPercentiles | None:
    """
    Return a player's full detail plus percentile ranks.

    Returns None if the player is not found.
    percentiles will be None when the peer group is too small.
    """
    player = get_player_by_id(player_id)
    if player is None:
        return None

    percentiles = get_player_percentiles(player_id)
    return PlayerDetailWithPercentiles(
        **player.model_dump(),
        percentiles=percentiles,
    )


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------


def rank_players(
    metric: str,
    *,
    position: str | None = None,
    league: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    min_minutes: int = DEFAULT_MIN_MINUTES,
    limit: int = 10,
) -> list[RankedPlayer]:
    """
    Return the top players sorted descending by the requested metric.

    metric    — any key from SUPPORTED_METRICS (per-90, _per90 alias, or raw)
    position  — exact position filter (case-insensitive), optional
    league    — exact league filter (case-insensitive), optional
    min_age   — inclusive lower bound on player age, optional
    max_age   — inclusive upper bound on player age, optional
    min_minutes — minimum minutes_played; applies to ALL metrics (default 300).
                  Per-90 metrics additionally enforce at least 1 minute to avoid
                  division by zero regardless of this value.
    limit     — number of results; clamped to MAX_RANK_LIMIT (50)

    Raises ValueError for unknown metric names.
    """
    if metric not in _METRIC_REGISTRY:
        supported = ", ".join(sorted(SUPPORTED_METRICS))
        raise ValueError(
            f"Unknown metric '{metric}'. Supported metrics: {supported}"
        )

    _col, label, is_per90 = _METRIC_REGISTRY[metric]
    # min_minutes applies to all metrics.
    # For per-90 metrics we additionally enforce at least 1 minute so we
    # never divide by zero; for raw metrics we honour whatever the caller passed.
    effective_min_minutes = max(1, min_minutes) if is_per90 else max(0, min_minutes)
    limit = min(max(1, limit), MAX_RANK_LIMIT)

    players = get_players(
        position=position,
        league=league,
        min_minutes=effective_min_minutes,
    )

    # age filters
    if min_age is not None:
        players = [p for p in players if p.age >= min_age]
    if max_age is not None:
        players = [p for p in players if p.age <= max_age]

    # compute metric value for each player
    scored: list[tuple[PlayerDetail, float]] = []
    for p in players:
        val = _get_metric_value(p, metric)
        if val is not None:
            scored.append((p, val))

    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:limit]

    return [
        RankedPlayer(
            rank=i + 1,
            player_id=p.player_id,
            name=p.name,
            club=p.club,
            league=p.league,
            position=p.position,
            metric_value=round(val, P90_ROUND),
            metric_label=label,
        )
        for i, (p, val) in enumerate(scored)
    ]

