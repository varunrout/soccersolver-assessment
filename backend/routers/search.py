"""
routers/search.py — GET /players/search

Implemented fully in Issue #8.
"""

from fastapi import APIRouter, HTTPException, Query

from models.player import PlayerSummary
from services import data_service

router = APIRouter()


@router.get("/search", response_model=list[PlayerSummary], summary="Search players by name")
def search_players(
    q: str = Query(..., description="Player name substring (case-insensitive)"),
) -> list[PlayerSummary]:
    """
    Case-insensitive substring search on player name.
    Returns an empty list (never 404) when no results are found.
    Empty or whitespace-only query returns HTTP 400.
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' must not be blank")
    return data_service.search_players(q)
