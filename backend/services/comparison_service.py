"""
comparison_service.py — single source of truth for two-player comparison.

Both GET /players/compare and POST /chat call compare_players().
No comparison logic lives anywhere else.

Implemented in Issue #7.
"""

from __future__ import annotations

from models.player import ComparisonResult


def compare_players(player_a_id: str, player_b_id: str) -> ComparisonResult:
    """
    Compare two players across per-90 metrics and market context.

    Raises fastapi.HTTPException(404) if either player_id is not found.

    Metrics compared (all per-90 normalised):
        goals, assists, shots, passes, xg, xa

    Winner per metric: higher value wins; draw if |a - b| < 0.01.
    """
    # TODO (Issue #7)
    raise NotImplementedError(
        "comparison_service.compare_players — implement in Issue #7"
    )
