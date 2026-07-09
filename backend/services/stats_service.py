"""
stats_service.py — deterministic percentile and ranking logic.

The LLM never calls these functions.  All numeric results come from here.

Implemented in Issue #6.
"""

from __future__ import annotations

from models.player import PlayerPercentiles, RankedPlayer


def get_player_percentiles(player_id: str) -> PlayerPercentiles | None:
    """
    Compute per-90 percentile ranks for a player vs their position+league peers.
    Returns None when the peer group has fewer than 5 players.

    Metrics: goals_p90, assists_p90, shots_p90, passes_p90, xg_p90, xa_p90
    """
    # TODO (Issue #6)
    raise NotImplementedError(
        "stats_service.get_player_percentiles — implement in Issue #6"
    )


def get_league_averages(position: str, league: str) -> dict[str, float]:
    """
    Return mean per-90 values for each metric within a position+league group.
    Keys: goals_p90, assists_p90, shots_p90, passes_p90, xg_p90, xa_p90
    """
    # TODO (Issue #6)
    raise NotImplementedError(
        "stats_service.get_league_averages — implement in Issue #6"
    )


def rank_players(
    metric: str,
    *,
    league: str | None = None,
    position: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    limit: int = 5,
) -> list[RankedPlayer]:
    """
    Return the top-N players sorted by a per-90 metric, with optional filters.
    metric must be one of: goals, assists, shots, passes, xg, xa
    (the service appends _p90 normalisation internally).
    """
    # TODO (Issue #6)
    raise NotImplementedError(
        "stats_service.rank_players — implement in Issue #6"
    )
