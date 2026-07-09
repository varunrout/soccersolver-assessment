"""
routers/search.py — GET /players/search

Implemented fully in Issue #8.
"""

from fastapi import APIRouter, Query

from models.player import PlayerSummary

router = APIRouter()


@router.get("/search", response_model=list[PlayerSummary], summary="Search players by name")
def search_players(
    q: str = Query(..., min_length=1, description="Player name (substring match)"),
) -> list[PlayerSummary]:
    """
    Case-insensitive substring search on player name.
    Returns an empty list (never 404) when no results are found.
    """
    # TODO (Issue #8): call services.data_service.search_players(q)
    return []
