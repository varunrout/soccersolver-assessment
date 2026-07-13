"""Optional, isolated player-image enrichment with bounded provider access."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

PROVIDER_TIMEOUT_SECONDS = 3.0
POSITIVE_CACHE_SECONDS = 24 * 60 * 60
NEGATIVE_CACHE_SECONDS = 5 * 60


class PlayerImageProvider(Protocol):
    def get_player_image(
        self,
        *,
        player_name: str,
        club: str,
        league: str,
    ) -> str | None:
        ...


def _valid_image_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value.strip()


class HttpPlayerImageProvider:
    """Calls a configured provider endpoint that returns `image_url` or `url`."""

    def __init__(self, *, base_url: str, api_key: str, timeout: float = PROVIDER_TIMEOUT_SECONDS):
        valid_base_url = _valid_image_url(base_url)
        if valid_base_url is None:
            raise ValueError("PLAYER_IMAGE_API_BASE_URL must be an http or https URL")
        self._base_url = valid_base_url
        self._api_key = api_key
        self._timeout = timeout

    def get_player_image(self, *, player_name: str, club: str, league: str) -> str | None:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        response = requests.get(
            self._base_url,
            params={"player_name": player_name, "club": club, "league": league},
            headers=headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return None
        return _valid_image_url(payload.get("image_url") or payload.get("url"))


@dataclass(frozen=True)
class _CacheEntry:
    image_url: str | None
    expires_at: float


_cache: dict[str, _CacheEntry] = {}
_cache_lock = Lock()


def _cache_key(*, player_name: str, club: str, league: str) -> str:
    return "|".join(part.strip().casefold() for part in (player_name, club, league))


def _configured_provider() -> PlayerImageProvider | None:
    provider_name = os.getenv("PLAYER_IMAGE_PROVIDER", "").strip().casefold()
    if not provider_name:
        return None
    if provider_name != "http":
        logger.warning("Unsupported player image provider configured: %s", provider_name)
        return None

    base_url = os.getenv("PLAYER_IMAGE_API_BASE_URL", "").strip()
    if not base_url:
        logger.warning("Player image provider configured without a base URL")
        return None

    try:
        return HttpPlayerImageProvider(
            base_url=base_url,
            api_key=os.getenv("PLAYER_IMAGE_API_KEY", "").strip(),
        )
    except ValueError:
        logger.warning("Player image provider has an invalid base URL")
        return None


def get_player_image(
    *,
    player_name: str,
    club: str,
    league: str,
    provider: PlayerImageProvider | None = None,
) -> str | None:
    """Resolve a safe image URL without allowing enrichment failures to escape."""
    key = _cache_key(player_name=player_name, club=club, league=league)
    now = time.monotonic()

    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached.expires_at > now:
            return cached.image_url
        if cached:
            _cache.pop(key, None)

    active_provider = provider or _configured_provider()
    image_url: str | None = None
    if active_provider is not None:
        try:
            image_url = _valid_image_url(
                active_provider.get_player_image(
                    player_name=player_name,
                    club=club,
                    league=league,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Player image lookup failed: %s", type(exc).__name__)

    ttl = POSITIVE_CACHE_SECONDS if image_url else NEGATIVE_CACHE_SECONDS
    with _cache_lock:
        _cache[key] = _CacheEntry(image_url=image_url, expires_at=now + ttl)
    return image_url


def clear_image_cache() -> None:
    """Clear process-local image cache; intended for tests and maintenance."""
    with _cache_lock:
        _cache.clear()