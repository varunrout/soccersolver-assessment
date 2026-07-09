"""
Player Pydantic models.

Hierarchy:
    PlayerSummary   — used by search results (list view)
    PlayerDetail    — used by the profile endpoint (full stats + percentiles)
    PlayerPercentiles   — per-metric percentile rank vs position+league peers
    RankedPlayer    — one entry in a ranking list (used by chat)
    ComparisonResult    — used by /players/compare and the chat comparison response
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Search / list
# ---------------------------------------------------------------------------


class PlayerSummary(BaseModel):
    player_id: str
    name: str
    position: Literal["GK", "DEF", "MID", "FWD"]
    club: str
    league: str
    market_value_eur: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Full profile
# ---------------------------------------------------------------------------


class PlayerDetail(PlayerSummary):
    age: int
    goals: int
    assists: int
    minutes_played: int
    shots: int
    passes: int
    xg: float
    xa: float


class PlayerPercentiles(BaseModel):
    player_id: str
    """
    Percentile rank (0–100) for each per-90 metric within the player's
    position + league peer group.  None when the peer group is too small (<5).
    """
    metrics: dict[str, float | None] = Field(
        default_factory=dict,
        examples=[{"goals_p90": 78.5, "assists_p90": 62.0, "xg_p90": 80.1}],
    )


class PlayerDetailWithPercentiles(PlayerDetail):
    percentiles: PlayerPercentiles | None = None


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------


class RankedPlayer(BaseModel):
    rank: int
    player_id: str
    name: str
    club: str
    league: str
    position: str
    metric_value: float
    metric_label: str


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


class MetricComparison(BaseModel):
    metric_name: str
    label: str
    value_a: float
    value_b: float
    winner: Literal["a", "b", "draw"]


class MarketContext(BaseModel):
    value_a: int
    value_b: int
    league_avg_a: int | None = None  # avg market value, same position+league as player A
    league_avg_b: int | None = None


class ComparisonResult(BaseModel):
    player_a: PlayerDetail
    player_b: PlayerDetail
    metrics: list[MetricComparison]
    market_context: MarketContext
