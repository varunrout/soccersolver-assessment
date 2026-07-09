"""
data_service.py — CSV data access layer.

All CSV reads go through this module.  No endpoint or service imports
pandas or reads the CSV directly.

Implemented in Issue #5.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from models.player import PlayerDetail, PlayerSummary

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: list[str] = [
    "player_id",
    "name",
    "position",
    "age",
    "club",
    "league",
    "market_value_eur",
    "goals",
    "assists",
    "minutes_played",
    "shots",
    "passes",
    "xg",
    "xa",
]

_STRING_COLS  = ["player_id", "name", "position", "club", "league"]
_INT_COLS     = ["age", "market_value_eur", "goals", "assists",
                 "minutes_played", "shots", "passes"]
_FLOAT_COLS   = ["xg", "xa"]
_REQUIRED_NON_EMPTY = ["player_id", "name", "position", "club", "league"]

SEARCH_LIMIT = 25

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_csv_path() -> Path:
    """
    Resolve the CSV path from the CSV_PATH env var or the default location.

    Supports:
    - Unset → <repo>/backend/data/players.csv (local dev)
    - Absolute path → used as-is (Docker: /app/backend/data/players.csv)
    - Relative path → joined onto the backend/ directory
    """
    env_val = os.getenv("CSV_PATH", "")
    if env_val:
        p = Path(env_val)
        return p if p.is_absolute() else Path(__file__).parent.parent / p
    return Path(__file__).parent.parent / "data" / "players.csv"


@lru_cache(maxsize=1)
def _load_df() -> pd.DataFrame:
    """
    Load, validate, and clean the player CSV.  Cached for the process lifetime.

    Raises
    ------
    FileNotFoundError   if the CSV file does not exist.
    ValueError          if required columns are missing or player_id is not unique.
    """
    path = _resolve_csv_path()
    if not path.exists():
        raise FileNotFoundError(f"players.csv not found at {path}")

    df = pd.read_csv(path, dtype=str)  # read everything as str first

    # --- column validation ---------------------------------------------------
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"players.csv is missing required columns: {missing}")

    # --- string cleaning -----------------------------------------------------
    for col in _STRING_COLS:
        df[col] = df[col].fillna("").str.strip()

    # --- non-empty validation ------------------------------------------------
    for col in _REQUIRED_NON_EMPTY:
        empty_count = (df[col] == "").sum()
        if empty_count:
            raise ValueError(
                f"players.csv has {empty_count} empty value(s) in required column '{col}'"
            )

    # --- numeric coercion ----------------------------------------------------
    for col in _INT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in _FLOAT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    # --- uniqueness check ----------------------------------------------------
    dupes = df["player_id"].duplicated()
    if dupes.any():
        dupe_ids = df.loc[dupes, "player_id"].tolist()
        raise ValueError(
            f"players.csv contains {dupes.sum()} duplicate player_id(s): {dupe_ids[:5]}"
        )

    return df.reset_index(drop=True)


def _row_to_summary(row: pd.Series) -> PlayerSummary:
    return PlayerSummary(
        player_id=row["player_id"],
        name=row["name"],
        position=row["position"],
        club=row["club"],
        league=row["league"],
        market_value_eur=int(row["market_value_eur"]),
    )


def _row_to_detail(row: pd.Series) -> PlayerDetail:
    return PlayerDetail(
        player_id=row["player_id"],
        name=row["name"],
        position=row["position"],
        club=row["club"],
        league=row["league"],
        market_value_eur=int(row["market_value_eur"]),
        age=int(row["age"]),
        goals=int(row["goals"]),
        assists=int(row["assists"]),
        minutes_played=int(row["minutes_played"]),
        shots=int(row["shots"]),
        passes=int(row["passes"]),
        xg=float(row["xg"]),
        xa=float(row["xa"]),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search_players(query: str) -> list[PlayerSummary]:
    """
    Case-insensitive substring search on player name.

    Ranking (best-first):
      1. Exact match (case-insensitive)
      2. Name starts with the query
      3. Any word in the name starts with the query
      4. Substring match anywhere in the name
    Within each tier, rows are sorted by minutes_played descending so
    higher-profile players surface first.

    Returns at most SEARCH_LIMIT (25) results.
    Empty or whitespace-only query returns an empty list.
    """
    q = query.strip()
    if not q:
        return []

    df = _load_df()
    q_lower = q.lower()
    name_lower = df["name"].str.lower()

    exact   = name_lower == q_lower
    prefix  = name_lower.str.startswith(q_lower) & ~exact
    word    = name_lower.str.contains(r"(?<![a-z])" + re.escape(q_lower),
                                      regex=True, na=False) & ~prefix & ~exact
    substr  = name_lower.str.contains(re.escape(q_lower),
                                      regex=False, na=False) & ~word & ~prefix & ~exact

    # assign tier label for sorting
    tier = pd.Series("", index=df.index)
    tier[exact]  = "1"
    tier[prefix] = "2"
    tier[word]   = "3"
    tier[substr] = "4"

    matched = df[tier != ""].copy()
    matched["_tier"] = tier[tier != ""]
    matched = (
        matched
        .sort_values(["_tier", "minutes_played"], ascending=[True, False])
        .head(SEARCH_LIMIT)
    )

    return [_row_to_summary(row) for _, row in matched.iterrows()]


def get_player_by_id(player_id: str) -> PlayerDetail | None:
    """
    Exact lookup by player_id.

    Returns None if no player with that id exists.
    """
    df = _load_df()
    mask = df["player_id"] == player_id
    if not mask.any():
        return None
    return _row_to_detail(df.loc[mask].iloc[0])


def get_players(
    *,
    position: str | None = None,
    league: str | None = None,
    min_minutes: int = 0,
) -> list[PlayerDetail]:
    """
    Return all players as PlayerDetail, sorted by minutes_played descending.

    Optional filters (all case-insensitive):
    - position  — exact match against the position column
    - league    — exact match against the league column
    - min_minutes — only return players with minutes_played >= this value
    """
    df = _load_df()
    mask = pd.Series(True, index=df.index)

    if position is not None:
        mask &= df["position"].str.lower() == position.strip().lower()

    if league is not None:
        mask &= df["league"].str.lower() == league.strip().lower()

    if min_minutes > 0:
        mask &= df["minutes_played"] >= min_minutes

    filtered = df.loc[mask].sort_values("minutes_played", ascending=False)
    return [_row_to_detail(row) for _, row in filtered.iterrows()]

