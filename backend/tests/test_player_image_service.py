from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from fastapi.testclient import TestClient

_BACKEND = Path(__file__).parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app
from services import player_image_service

SALAH_ID = "e342ad68"
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_image_configuration():
    player_image_service.clear_image_cache()
    with patch.dict(os.environ, {}, clear=False):
        for key in (
            "PLAYER_IMAGE_PROVIDER",
            "PLAYER_IMAGE_API_KEY",
            "PLAYER_IMAGE_API_BASE_URL",
        ):
            os.environ.pop(key, None)
        yield
    player_image_service.clear_image_cache()


def test_no_provider_configured_returns_no_image_safely():
    response = client.get(f"/players/{SALAH_ID}/image")

    assert response.status_code == 200
    assert response.json() == {"player_id": SALAH_ID, "image_url": None}


def test_unknown_player_returns_404_without_provider_lookup():
    response = client.get("/players/not-a-player/image")

    assert response.status_code == 404


def test_provider_success_returns_valid_url():
    provider = Mock()
    provider.get_player_image.return_value = "https://images.example.test/salah.jpg"

    result = player_image_service.get_player_image(
        player_name="Mohamed Salah",
        club="Liverpool",
        league="Premier League",
        provider=provider,
    )

    assert result == "https://images.example.test/salah.jpg"


@pytest.mark.parametrize("failure", [requests.Timeout(), RuntimeError("provider down")])
def test_provider_failure_returns_none(failure: Exception):
    provider = Mock()
    provider.get_player_image.side_effect = failure

    result = player_image_service.get_player_image(
        player_name="Mohamed Salah",
        club="Liverpool",
        league="Premier League",
        provider=provider,
    )

    assert result is None


@pytest.mark.parametrize(
    "unsafe_url",
    ["javascript:alert(1)", "data:image/png;base64,abc", "//example.test/player.jpg", "not a url"],
)
def test_invalid_provider_url_is_rejected(unsafe_url: str):
    provider = Mock()
    provider.get_player_image.return_value = unsafe_url

    result = player_image_service.get_player_image(
        player_name="Mohamed Salah",
        club="Liverpool",
        league="Premier League",
        provider=provider,
    )

    assert result is None


def test_positive_cache_prevents_duplicate_provider_calls():
    provider = Mock()
    provider.get_player_image.return_value = "https://images.example.test/salah.jpg"
    identity = {
        "player_name": "Mohamed Salah",
        "club": "Liverpool",
        "league": "Premier League",
        "provider": provider,
    }

    first = player_image_service.get_player_image(**identity)
    second = player_image_service.get_player_image(**identity)

    assert first == second
    provider.get_player_image.assert_called_once()


def test_negative_cache_prevents_duplicate_failed_lookups():
    provider = Mock()
    provider.get_player_image.return_value = None
    identity = {
        "player_name": "Mohamed Salah",
        "club": "Liverpool",
        "league": "Premier League",
        "provider": provider,
    }

    assert player_image_service.get_player_image(**identity) is None
    assert player_image_service.get_player_image(**identity) is None
    provider.get_player_image.assert_called_once()


def test_image_lookup_does_not_change_player_statistics_response():
    before = client.get(f"/players/{SALAH_ID}").json()
    client.get(f"/players/{SALAH_ID}/image")
    after = client.get(f"/players/{SALAH_ID}").json()

    assert after == before
    assert "image_url" not in after


def test_api_key_is_never_in_endpoint_response():
    with patch.dict(
        os.environ,
        {
            "PLAYER_IMAGE_PROVIDER": "http",
            "PLAYER_IMAGE_API_KEY": "super-secret-key",
            "PLAYER_IMAGE_API_BASE_URL": "https://provider.example.test/player",
        },
    ), patch("services.player_image_service.requests.get") as request_get:
        request_get.side_effect = requests.Timeout()
        response = client.get(f"/players/{SALAH_ID}/image")

    assert response.status_code == 200
    assert "super-secret-key" not in response.text


def test_http_provider_uses_bounded_timeout_and_backend_authorization_header():
    provider = player_image_service.HttpPlayerImageProvider(
        base_url="https://provider.example.test/player",
        api_key="secret",
    )
    response = Mock()
    response.json.return_value = {"image_url": "https://cdn.example.test/player.jpg"}
    response.raise_for_status.return_value = None

    with patch("services.player_image_service.requests.get", return_value=response) as request_get:
        result = provider.get_player_image(
            player_name="Mohamed Salah",
            club="Liverpool",
            league="Premier League",
        )

    assert result == "https://cdn.example.test/player.jpg"
    assert request_get.call_args.kwargs["timeout"] == player_image_service.PROVIDER_TIMEOUT_SECONDS
    assert request_get.call_args.kwargs["headers"]["Authorization"] == "Bearer secret"