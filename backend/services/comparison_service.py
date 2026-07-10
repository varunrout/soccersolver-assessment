"""
comparison_service.py — single source of truth for two-player comparison.

Both GET /players/compare and POST /chat call compare_players().
No comparison logic lives anywhere else.

Implemented in Issue #7.
"""

from __future__ import annotations

from typing import Literal

from models.player import (
    ComparisonResult,
    MarketContext,
    MetricComparison,
    PlayerDetail,
)
from services.data_service import get_player_by_id, get_players
from services.stats_service import DEFAULT_MIN_MINUTES, P90_ROUND, _per90

# ---------------------------------------------------------------------------
# Metric definitions for comparison (metric_name, raw_column, human_label)
# ---------------------------------------------------------------------------

_COMPARISON_METRICS: list[tuple[str, str, str]] = [
    ("goals_p90",   "goals",   "Goals per 90"),
    ("assists_p90", "assists", "Assists per 90"),
    ("shots_p90",   "shots",   "Shots per 90"),
    ("passes_p90",  "passes",  "Passes per 90"),
    ("xg_p90",      "xg",      "xG per 90"),
    ("xa_p90",      "xa",      "xA per 90"),
]

# Differences within this tolerance are treated as a draw.
DRAW_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric_winner(value_a: float, value_b: float) -> Literal["a", "b", "draw"]:
    """
    Return which player wins a metric.

    Values within DRAW_TOLERANCE (0.01) of each other are a draw so that
    negligible per-90 differences are not surfaced as meaningful wins.
    The difference is rounded to 10 decimal places before comparison to avoid
    IEEE 754 representation noise (e.g. 0.46 - 0.45 = 0.010000000000000009).
    """
    diff = round(abs(value_a - value_b), 10)
    if diff <= DRAW_TOLERANCE:
        return "draw"
    return "a" if value_a > value_b else "b"


def _safe_per90(player: PlayerDetail, col: str) -> float:
    """
    Per-90 value for `col`, rounded to P90_ROUND decimals.
    Returns 0.0 when minutes_played <= 0 so comparisons never crash.
    """
    val = _per90(float(getattr(player, col)), player.minutes_played)
    return val if val is not None else 0.0


def _average_market_value(
    position: str,
    league: str,
    min_minutes: int = DEFAULT_MIN_MINUTES,
) -> int | None:
    """
    Mean market value (EUR, rounded to int) for position+league peers.
    Returns None when the peer group is empty.
    """
    peers = get_players(position=position, league=league, min_minutes=min_minutes)
    if not peers:
        return None
    return round(sum(p.market_value_eur for p in peers) / len(peers))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare_players(player_a_id: str, player_b_id: str) -> ComparisonResult | None:
    """
    Compare two players across six per-90 metrics and market context.

    Returns None if either player_id is not found.

    Metrics: goals, assists, shots, passes, xG, xA — all per 90 minutes.
    Zero-minute players contribute 0.0 for every metric (no crash, no fabrication).
    """
    player_a = get_player_by_id(player_a_id)
    player_b = get_player_by_id(player_b_id)
    if player_a is None or player_b is None:
        return None

    metrics: list[MetricComparison] = []
    for metric_name, col, label in _COMPARISON_METRICS:
        val_a = round(_safe_per90(player_a, col), P90_ROUND)
        val_b = round(_safe_per90(player_b, col), P90_ROUND)
        metrics.append(
            MetricComparison(
                metric_name=metric_name,
                label=label,
                value_a=val_a,
                value_b=val_b,
                winner=_metric_winner(val_a, val_b),
            )
        )

    market_context = MarketContext(
        value_a=player_a.market_value_eur,
        value_b=player_b.market_value_eur,
        league_avg_a=_average_market_value(player_a.position, player_a.league),
        league_avg_b=_average_market_value(player_b.position, player_b.league),
    )

    return ComparisonResult(
        player_a=player_a,
        player_b=player_b,
        metrics=metrics,
        market_context=market_context,
    )
