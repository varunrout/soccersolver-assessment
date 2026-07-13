"""Player image presentation endpoint, isolated from statistics responses."""

from fastapi import APIRouter, HTTPException

from models.player import PlayerImageResponse
from services import data_service, player_image_service

router = APIRouter()


@router.get(
    "/{player_id}/image",
    response_model=PlayerImageResponse,
    summary="Resolve an optional player image",
)
def get_player_image(player_id: str) -> PlayerImageResponse:
    player = data_service.get_player_by_id(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    image_url = player_image_service.get_player_image(
        player_name=player.name,
        club=player.club,
        league=player.league,
    )
    return PlayerImageResponse(player_id=player.player_id, image_url=image_url)