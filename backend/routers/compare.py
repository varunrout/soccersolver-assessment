"""
routers/compare.py — GET /players/compare?player_a_id={id}&player_b_id={id}

Implemented fully in Issue #8.

NOTE: this router must be registered BEFORE routers/profile.py in main.py,
otherwise FastAPI will try to match 'compare' as a {player_id} path param.
"""

from fastapi import APIRouter, HTTPException, Query

from models.player import ComparisonResult
from services import comparison_service

router = APIRouter()


@router.get(
    "/compare",
    response_model=ComparisonResult,
    summary="Compare two players side by side",
)
def compare_players(
    player_a_id: str = Query(..., description="player_id of player A"),
    player_b_id: str = Query(..., description="player_id of player B"),
) -> ComparisonResult:
    """
    Returns a structured per-metric comparison of two players.
    Returns 404 if either player_id is not found.
    """
    result = comparison_service.compare_players(player_a_id, player_b_id)
    if result is None:
        raise HTTPException(status_code=404, detail="One or both players not found")
    return result
