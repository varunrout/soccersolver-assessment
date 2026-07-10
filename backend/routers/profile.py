"""
routers/profile.py — GET /players/{player_id}

Implemented fully in Issue #8.
"""

from fastapi import APIRouter, HTTPException

from models.player import PlayerDetailWithPercentiles
from services import stats_service

router = APIRouter()


@router.get(
    "/{player_id}",
    response_model=PlayerDetailWithPercentiles,
    summary="Get player profile with contextualised metrics",
)
def get_player(player_id: str) -> PlayerDetailWithPercentiles:
    """
    Returns full player profile including per-90 percentile ranks
    vs position+league peers.
    Returns 404 if the player_id does not exist.
    """
    profile = stats_service.get_player_profile_stats(player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return profile
