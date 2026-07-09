"""
routers/profile.py — GET /players/{player_id}

Implemented fully in Issue #8.
"""

from fastapi import APIRouter, HTTPException

from models.player import PlayerDetailWithPercentiles

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
    # TODO (Issue #8): call data_service.get_player_by_id + stats_service.get_player_percentiles
    raise HTTPException(status_code=501, detail="Not implemented yet — Issue #8")
