"""Optional, isolated player-image enrichment with bounded provider access."""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from urllib.parse import quote, urlparse

import requests

logger = logging.getLogger(__name__)

PROVIDER_TIMEOUT_SECONDS = 3.0
POSITIVE_CACHE_SECONDS = 24 * 60 * 60
NEGATIVE_CACHE_SECONDS = 5 * 60
SPORTMONKS_PROVIDER_NAME = "sportmonks"
SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"

LEAGUE_COUNTRY_ALIASES = {
    "premier league": {"england", "english"},
    "la liga": {"spain", "spanish"},
    "bundesliga": {"germany", "german"},
    "serie a": {"italy", "italian"},
    "ligue 1": {"france", "french"},
}


class PlayerImageProvider(Protocol):
    def get_player_image(
        self,
        *,
        player_name: str,
        club: str,
        league: str,
    ) -> str | None:
        ...


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(character for character in normalized if not unicodedata.combining(character))
    collapsed = re.sub(r"[^a-z0-9]+", " ", ascii_only.casefold())
    return " ".join(collapsed.split())


def _normalized_names(candidate: dict[str, object]) -> set[str]:
    possible_names = {
        candidate.get("name"),
        candidate.get("display_name"),
        candidate.get("common_name"),
    }
    firstname = candidate.get("firstname")
    lastname = candidate.get("lastname")
    if isinstance(firstname, str) and isinstance(lastname, str):
        possible_names.add(f"{firstname} {lastname}")
    return {
        _normalize_text(name)
        for name in possible_names
        if isinstance(name, str) and _normalize_text(name)
    }


def _candidate_team_names(candidate: dict[str, object]) -> set[str]:
    names: set[str] = set()
    teams = candidate.get("teams")
    if not isinstance(teams, list):
        return names
    for team_entry in teams:
        if not isinstance(team_entry, dict):
            continue
        team = team_entry.get("team")
        if not isinstance(team, dict):
            continue
        name = team.get("name")
        if isinstance(name, str):
            normalized = _normalize_text(name)
            if normalized:
                names.add(normalized)
    return names


def _candidate_country_names(candidate: dict[str, object]) -> set[str]:
    countries: set[str] = set()
    for key in ("country", "nationality"):
        entity = candidate.get(key)
        if isinstance(entity, dict):
            name = entity.get("name")
            if isinstance(name, str):
                normalized = _normalize_text(name)
                if normalized:
                    countries.add(normalized)

    teams = candidate.get("teams")
    if isinstance(teams, list):
        for team_entry in teams:
            if not isinstance(team_entry, dict):
                continue
            team = team_entry.get("team")
            if not isinstance(team, dict):
                continue
            country = team.get("country")
            if not isinstance(country, dict):
                continue
            name = country.get("name")
            if isinstance(name, str):
                normalized = _normalize_text(name)
                if normalized:
                    countries.add(normalized)
    return countries


def _league_country_aliases(league: str) -> set[str]:
    normalized_league = _normalize_text(league)
    aliases = LEAGUE_COUNTRY_ALIASES.get(normalized_league, set())
    return {normalized_league, *aliases} if normalized_league else set(aliases)


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
class _SportmonksCandidate:
    image_url: str | None
    name_match: bool
    club_match: bool
    league_match: bool


def _sportmonks_candidate(candidate: object, *, player_name: str, club: str, league: str) -> _SportmonksCandidate | None:
    if not isinstance(candidate, dict):
        return None

    normalized_player_name = _normalize_text(player_name)
    candidate_names = _normalized_names(candidate)
    if normalized_player_name not in candidate_names:
        return None

    normalized_club = _normalize_text(club)
    club_match = bool(normalized_club) and normalized_club in _candidate_team_names(candidate)

    candidate_countries = _candidate_country_names(candidate)
    league_aliases = _league_country_aliases(league)
    league_match = bool(candidate_countries.intersection(league_aliases))

    return _SportmonksCandidate(
        image_url=_valid_image_url(candidate.get("image_path")),
        name_match=True,
        club_match=club_match,
        league_match=league_match,
    )


def _select_sportmonks_image(*, payload: object, player_name: str, club: str, league: str) -> str | None:
    if not isinstance(payload, dict):
        return None

    raw_candidates = payload.get("data")
    if not isinstance(raw_candidates, list):
        return None

    candidates = [
        candidate
        for candidate in (
            _sportmonks_candidate(item, player_name=player_name, club=club, league=league)
            for item in raw_candidates
        )
        if candidate is not None
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: (
            candidate.club_match,
            candidate.league_match,
            candidate.image_url is not None,
        ),
        reverse=True,
    )
    best = candidates[0]
    if best.image_url is None:
        return None

    equally_ranked = [
        candidate
        for candidate in candidates
        if (
            candidate.club_match,
            candidate.league_match,
            candidate.image_url is not None,
        )
        == (
            best.club_match,
            best.league_match,
            best.image_url is not None,
        )
    ]

    if len(candidates) == 1:
        return best.image_url
    if best.club_match:
        return best.image_url if len(equally_ranked) == 1 else None
    if best.league_match:
        return best.image_url if len(equally_ranked) == 1 else None
    return None


class SportmonksPlayerImageProvider:
    """Uses Sportmonks player search with deterministic disambiguation."""

    def __init__(self, *, api_token: str, timeout: float = PROVIDER_TIMEOUT_SECONDS):
        if not api_token.strip():
            raise ValueError("PLAYER_IMAGE_API_KEY is required for the sportmonks provider")
        self._api_token = api_token.strip()
        self._timeout = timeout

    def get_player_image(self, *, player_name: str, club: str, league: str) -> str | None:
        response = requests.get(
            f"{SPORTMONKS_BASE_URL}/players/search/{quote(player_name)}",
            params={"include": "teams.team.country;country;nationality"},
            headers={"Accept": "application/json", "Authorization": self._api_token},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return _select_sportmonks_image(
            payload=response.json(),
            player_name=player_name,
            club=club,
            league=league,
        )


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
    if provider_name == SPORTMONKS_PROVIDER_NAME:
        api_key = os.getenv("PLAYER_IMAGE_API_KEY", "").strip()
        if not api_key:
            logger.warning("Sportmonks player image provider configured without an API token")
            return None
        try:
            return SportmonksPlayerImageProvider(api_token=api_key)
        except ValueError:
            logger.warning("Sportmonks player image provider has invalid configuration")
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