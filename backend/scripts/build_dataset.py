"""
build_dataset.py
----------------
Fetches StatsBomb open-data via kloppy (event + lineup files) for three full
league seasons (La Liga, Premier League, Serie A – all 2015/2016) and
aggregates per-player statistics.

Market value is not available in StatsBomb open-data, so we derive a
plausible proxy value from performance metrics, position, age, and league.

Output: backend/data/players.csv
"""

import json
import logging
import math
import random
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COMPETITIONS = [
    {"competition_id": 11, "season_id": 27, "league": "La Liga"},
    {"competition_id": 2,  "season_id": 27, "league": "Premier League"},
    {"competition_id": 12, "season_id": 27, "league": "Serie A"},
    # Extra partial seasons for more diversity
    {"competition_id": 9,  "season_id": 27, "league": "Bundesliga"},
    {"competition_id": 7,  "season_id": 108, "league": "Ligue 1"},
    {"competition_id": 11, "season_id": 90,  "league": "La Liga"},
]

SB_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
MAX_WORKERS = 6
RANDOM_SEED = 42
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "players.csv"

# Position normalisation map
POSITION_MAP = {
    "Goalkeeper": "GK",
    "Right Back": "DEF", "Left Back": "DEF",
    "Right Center Back": "DEF", "Left Center Back": "DEF",
    "Center Back": "DEF",
    "Right Wing Back": "MID", "Left Wing Back": "MID",
    "Right Defensive Midfield": "MID", "Left Defensive Midfield": "MID",
    "Center Defensive Midfield": "MID",
    "Right Center Midfield": "MID", "Left Center Midfield": "MID",
    "Center Midfield": "MID",
    "Right Midfield": "MID", "Left Midfield": "MID",
    "Right Attacking Midfield": "MID", "Left Attacking Midfield": "MID",
    "Center Attacking Midfield": "MID",
    "Right Wing": "FWD", "Left Wing": "FWD",
    "Right Center Forward": "FWD", "Left Center Forward": "FWD",
    "Center Forward": "FWD",
    "Secondary Striker": "FWD",
}

# Base market-value (EUR) by position
BASE_VALUE = {"GK": 3_000_000, "DEF": 8_000_000, "MID": 12_000_000, "FWD": 15_000_000}

# League prestige multiplier
LEAGUE_MULT = {
    "La Liga": 1.4,
    "Premier League": 1.6,
    "Serie A": 1.2,
    "Bundesliga": 1.3,
    "Ligue 1": 1.1,
}

random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> list | dict | None:
    import time
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 429:
                wait = RETRY_BACKOFF * attempt
                log.debug("Rate limited on %s, waiting %.1fs (attempt %d)", url, wait, attempt)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as exc:
            if attempt == MAX_RETRIES:
                log.warning("Failed to fetch %s after %d attempts: %s", url, MAX_RETRIES, exc)
                return None
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", url, exc)
            return None
    return None


def get_match_ids(competition_id: int, season_id: int) -> list[dict]:
    url = f"{SB_BASE}/matches/{competition_id}/{season_id}.json"
    matches = fetch_json(url) or []
    return matches


# ---------------------------------------------------------------------------
# Per-match processing (raw StatsBomb JSON — fast, no coordinate normalisation
# needed for aggregate stats)
# ---------------------------------------------------------------------------

def process_match(match_meta: dict, league: str) -> list[dict]:
    """
    Returns a list of per-player row dicts for one match.
    Extracts from lineup + event files directly.
    """
    match_id = match_meta["match_id"]
    season   = match_meta.get("season", {}).get("season_name", "")
    home_team = match_meta.get("home_team", {}).get("home_team_name", "")
    away_team = match_meta.get("away_team", {}).get("away_team_name", "")

    lineup_url = f"{SB_BASE}/lineups/{match_id}.json"
    events_url = f"{SB_BASE}/events/{match_id}.json"

    lineup_data = fetch_json(lineup_url)
    events_data = fetch_json(events_url)

    if not lineup_data or not events_data:
        return []

    # --- Build player registry from lineups ---
    players: dict[str, dict] = {}  # player_id -> info
    for team in lineup_data:
        team_name = team["team_name"]
        for p in team.get("lineup", []):
            pid     = str(p["player_id"])
            name    = p["player_name"]
            raw_pos = p.get("positions", [{}])[0].get("position", "Unknown") if p.get("positions") else "Unknown"
            pos     = POSITION_MAP.get(raw_pos, "MID")

            # minutes: look for substitution events later; default full match
            players[pid] = {
                "player_id": pid,
                "name": name,
                "position": pos,
                "club": team_name,
                "league": league,
                "season": season,
                "goals": 0,
                "assists": 0,
                "shots": 0,
                "passes": 0,
                "minutes_played": 90,
                "xg": 0.0,
                "xa": 0.0,
            }

    # --- Aggregate events ---
    for ev in events_data:
        pid = str(ev.get("player", {}).get("id", "")) if ev.get("player") else ""
        if not pid or pid not in players:
            continue

        etype = ev.get("type", {}).get("name", "")

        if etype == "Shot":
            shot = ev.get("shot", {})
            players[pid]["shots"] += 1
            players[pid]["xg"] += float(shot.get("statsbomb_xg", 0) or 0)
            if shot.get("outcome", {}).get("name") == "Goal":
                players[pid]["goals"] += 1

        elif etype == "Pass":
            players[pid]["passes"] += 1
            pass_info = ev.get("pass", {})
            players[pid]["xa"] += float(pass_info.get("xa", 0) or 0)
            if pass_info.get("goal_assist"):
                players[pid]["assists"] += 1

        elif etype == "Substitution":
            # Player being subbed off — update minutes from event timestamp
            minute = ev.get("minute", 90)
            players[pid]["minutes_played"] = minute

    return list(players.values())


# ---------------------------------------------------------------------------
# Market value estimation
# ---------------------------------------------------------------------------

def estimate_market_value(row: pd.Series) -> float:
    pos    = row.get("position", "MID")
    league = row.get("league", "La Liga")
    mp     = max(float(row.get("minutes_played_total", 0)), 1)
    age    = float(row.get("age", 25))

    # Performance score (per-90 weighted)
    p90 = mp / 90
    goals   = float(row.get("goals", 0))
    assists = float(row.get("assists", 0))
    xg      = float(row.get("xg", 0))

    perf = (goals * 3 + assists * 2 + xg * 1.5) / max(p90, 1)
    perf_mult = 1.0 + perf * 0.25

    # Age multiplier (peak = 26)
    age_mult = max(0.4, 1.5 - abs(age - 26) * 0.07)

    base    = BASE_VALUE.get(pos, 10_000_000)
    lg_mult = LEAGUE_MULT.get(league, 1.0)

    value = base * perf_mult * age_mult * lg_mult

    # Add noise ±25 %
    noise = random.uniform(0.75, 1.25)
    return round(value * noise / 100_000) * 100_000  # round to nearest 100k


# ---------------------------------------------------------------------------
# Name → approximate age lookup (not available in StatsBomb free data,
# so we assign a plausible age based on a hash of the player name)
# ---------------------------------------------------------------------------

def name_to_age(name: str) -> int:
    h = abs(hash(name)) % 100
    # Distribute ages 18-38, peak around 25-28
    age = 18 + int(h * 0.20)
    return min(age, 38)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    all_rows: list[dict] = []

    # Step 1: Gather all (match_meta, league) pairs
    log.info("Fetching match lists for %d competitions...", len(COMPETITIONS))
    match_tasks: list[tuple[dict, str]] = []
    for comp in COMPETITIONS:
        matches = get_match_ids(comp["competition_id"], comp["season_id"])
        log.info("  %s: %d matches", comp["league"], len(matches))
        for m in matches:
            match_tasks.append((m, comp["league"]))

    log.info("Total matches to process: %d", len(match_tasks))

    # Step 2: Process matches in parallel
    processed = 0
    failed    = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(process_match, meta, league): (meta["match_id"], league)
            for meta, league in match_tasks
        }
        for future in as_completed(futures):
            match_id, league = futures[future]
            try:
                rows = future.result()
                all_rows.extend(rows)
                processed += 1
                if processed % 50 == 0:
                    log.info("  Processed %d / %d matches...", processed, len(match_tasks))
            except Exception as exc:
                failed += 1
                log.warning("Match %s (%s) failed: %s", match_id, league, exc)

    log.info("Done: %d processed, %d failed. Raw player rows: %d", processed, failed, len(all_rows))

    # Step 3: Aggregate per player (sum stats across all their matches)
    df = pd.DataFrame(all_rows)
    if df.empty:
        log.error("No data collected. Exiting.")
        sys.exit(1)

    # For players appearing in multiple matches, sum numeric stats
    agg = (
        df.groupby("player_id")
        .agg(
            name             = ("name", "first"),
            position         = ("position", lambda x: x.mode()[0]),
            club             = ("club", "last"),   # most recent club
            league           = ("league", "last"),
            goals            = ("goals", "sum"),
            assists          = ("assists", "sum"),
            shots            = ("shots", "sum"),
            passes           = ("passes", "sum"),
            minutes_played_total = ("minutes_played", "sum"),
            xg               = ("xg", "sum"),
            xa               = ("xa", "sum"),
        )
        .reset_index()
    )

    # Step 4: Age + market value
    agg["age"] = agg["name"].apply(name_to_age)
    agg["market_value_eur"] = agg.apply(estimate_market_value, axis=1)

    # Step 5: Rename minutes column for API consistency
    agg.rename(columns={"minutes_played_total": "minutes_played"}, inplace=True)

    # Step 6: Filter to players with meaningful playing time (>= 90 minutes total)
    agg = agg[agg["minutes_played"] >= 90].copy()

    # Step 7: Round floats
    agg["xg"] = agg["xg"].round(2)
    agg["xa"] = agg["xa"].round(2)

    log.info("Unique players (>= 90 min): %d", len(agg))

    # Step 8: Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUTPUT_PATH, index=False)
    log.info("Saved to %s", OUTPUT_PATH)

    # Quick sanity check
    log.info("\n--- Sample (5 rows) ---")
    print(agg[["name", "position", "club", "league", "goals", "assists",
               "minutes_played", "xg", "market_value_eur"]].head(5).to_string())
    log.info("\n--- Per-league player counts ---")
    print(agg.groupby("league")["player_id"].count().to_string())
    log.info("\n--- Per-position counts ---")
    print(agg.groupby("position")["player_id"].count().to_string())


if __name__ == "__main__":
    main()
