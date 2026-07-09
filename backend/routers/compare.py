"""
routers/compare.py — GET /players/compare?a={id}&b={id}

Implemented fully in Issue #8.

NOTE: this router must be registered BEFORE routers/profile.py in main.py,
otherwise FastAPI will try to match 'compare' as a {player_id} path param.
"""

from fastapi import APIRouter, HTTPException, Query

from models.player import ComparisonResult

router = APIRouter()


@router.get(
    "/compare",
    response_model=ComparisonResult,
    summary="Compare two players side by side",
)
def compare_players(
    a: str = Query(..., description="player_id of player A"),
    b: str = Query(..., description="player_id of player B"),
) -> ComparisonResult:
    """
    Returns a structured per-metric comparison.
    Returns 404 if either player_id is not found.
    """
    # TODO (Issue #8): call comparison_service.compare_players(a, b)
    raise HTTPException(status_code=501, detail="Not implemented yet — Issue #8")
