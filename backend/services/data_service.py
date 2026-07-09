"""
data_service.py — CSV data access layer.

All CSV reads go through this module.  No endpoint or service imports
pandas or reads the CSV directly.

Implemented in Issue #5.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from models.player import PlayerDetail, PlayerSummary

_CSV_PATH = Path(__file__).parent.parent / os.getenv("CSV_PATH", "data/players.csv")


@lru_cache(maxsize=1)
def _load_df() -> pd.DataFrame:
    """Load and cache the player CSV on first access."""
    # TODO (Issue #5): implement full loading with NaN handling and
    #   deduplication of any residual duplicate player_ids.
    raise NotImplementedError("data_service._load_df — implement in Issue #5")


def search_players(query: str) -> list[PlayerSummary]:
    """Case-insensitive substring search on player name."""
    # TODO (Issue #5)
    raise NotImplementedError("data_service.search_players — implement in Issue #5")


def get_player_by_id(player_id: str) -> PlayerDetail | None:
    """Return a single PlayerDetail, or None if not found."""
    # TODO (Issue #5)
    raise NotImplementedError("data_service.get_player_by_id — implement in Issue #5")


def get_players(
    *,
    position: str | None = None,
    league: str | None = None,
    min_minutes: int = 0,
) -> list[PlayerDetail]:
    """Return all players, optionally filtered by position/league/minutes."""
    # TODO (Issue #5)
    raise NotImplementedError("data_service.get_players — implement in Issue #5")
