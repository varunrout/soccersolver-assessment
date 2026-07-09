"""
build_dataset.py
----------------
Downloads pre-compiled FBref player season statistics from the
worldfootballR_data GitHub repository (R RDS files, read via pyreadr)
and builds backend/data/players.csv.

Source:  https://github.com/JaseZiv/worldfootballR_data
License: Data originates from FBref (Sports Reference LLC).
         worldfootballR_data is a public mirror of that data.
         Use is subject to FBref's terms of service.
         This script is for educational / non-commercial use only.

Run once:
    pip install requests pyreadr pandas
    python backend/scripts/build_dataset.py

Output: backend/data/players.csv
"""

import logging
import os
import re
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pyreadr
import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "players.csv"

WORLDFOOTBALLR_BASE = (
    "https://github.com/JaseZiv/worldfootballR_data/raw/master"
    "/data/fb_big5_advanced_season_stats/"
)

# Use 2021-22 season (season_end_year=2022): most complete season in the mirror
TARGET_SEASON = 2022

# Position normalisation: FBref uses "FW", "MF", "DF", "GK" and combos like "MF,FW"
POSITION_MAP = {
    "GK": "GK",
    "DF": "DEF",
    "MF": "MID",
    "FW": "FWD",
}

# League display names
LEAGUE_CLEAN = {
    "Premier League": "Premier League",
    "La Liga": "La Liga",
    "Serie A": "Serie A",
    "Bundesliga": "Bundesliga",
    "Ligue 1": "Ligue 1",
}

# Market-value tier table (EUR) — deterministic, position+league+performance quartile
# IMPORTANT: these are ESTIMATES, not Transfermarkt values. See data/README.md.
MV_TIERS = {
    # (position, quartile) -> value EUR
    # quartile: 0=bottom25, 1=mid50, 2=upper25, 3=top10
    ("GK",  0): 1_000_000,  ("GK",  1): 3_500_000,  ("GK",  2): 9_000_000,  ("GK",  3): 22_000_000,
    ("DEF", 0): 1_500_000,  ("DEF", 1): 5_000_000,  ("DEF", 2): 14_000_000, ("DEF", 3): 35_000_000,
    ("MID", 0): 2_000_000,  ("MID", 1): 7_000_000,  ("MID", 2): 18_000_000, ("MID", 3): 45_000_000,
    ("FWD", 0): 2_500_000,  ("FWD", 1): 9_000_000,  ("FWD", 2): 25_000_000, ("FWD", 3): 65_000_000,
}

LEAGUE_MV_MULT = {
    "Premier League": 1.6,
    "La Liga": 1.4,
    "Bundesliga": 1.3,
    "Serie A": 1.2,
    "Ligue 1": 1.1,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def download_rds(filename: str) -> pd.DataFrame:
    url = WORLDFOOTBALLR_BASE + filename
    log.info("Downloading %s ...", filename)
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    log.info("  %.0f KB received", len(r.content) / 1024)
    with tempfile.NamedTemporaryFile(suffix=".rds", delete=False) as tmp:
        tmp.write(r.content)
        tmp_path = tmp.name
    try:
        result = pyreadr.read_r(tmp_path)
        return list(result.values())[0]
    finally:
        os.unlink(tmp_path)


def extract_player_id(url: str) -> str:
    """Extract FBref player hash from URL, e.g. '/en/players/39168d69/...' -> '39168d69'."""
    if not isinstance(url, str):
        return ""
    m = re.search(r"/players/([a-f0-9]+)/", url)
    return m.group(1) if m else ""


def normalise_position(raw: str) -> str:
    """FBref positions are like 'MF', 'FW,MF', 'DF,MF'. Use the primary (first) tag."""
    if not isinstance(raw, str) or not raw.strip():
        return "MID"
    primary = raw.split(",")[0].strip().upper()
    return POSITION_MAP.get(primary, "MID")


def performance_quartile(row: pd.Series, thresholds: dict) -> int:
    """
    Score a player by xG+xA per-90 and return their quartile bucket.
    thresholds: {pos: (q25, q75, q90)} precomputed from the full dataframe.
    """
    pos = row["position"]
    p90 = row.get("mins_per_90", 1) or 1
    xg  = float(row.get("xg", 0) or 0)
    xa  = float(row.get("xa", 0) or 0)
    score = (xg + xa) / p90
    q25, q75, q90 = thresholds.get(pos, (0.05, 0.20, 0.40))
    if score >= q90:
        return 3
    if score >= q75:
        return 2
    if score >= q25:
        return 1
    return 0


def estimate_market_value(row: pd.Series, thresholds: dict) -> int:
    pos     = row["position"]
    league  = row["league"]
    q       = performance_quartile(row, thresholds)
    base    = MV_TIERS.get((pos, q), 5_000_000)
    mult    = LEAGUE_MV_MULT.get(league, 1.0)
    return int(round(base * mult / 100_000) * 100_000)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ------------------------------------------------------------------
    # 1. Download RDS files
    # ------------------------------------------------------------------
    df_std   = download_rds("big5_player_standard.rds")
    df_shoot = download_rds("big5_player_shooting.rds")
    df_pass  = download_rds("big5_player_passing.rds")

    # ------------------------------------------------------------------
    # 2. Filter to target season
    # ------------------------------------------------------------------
    log.info("Filtering to season_end_year = %d ...", TARGET_SEASON)
    std   = df_std[df_std["Season_End_Year"] == TARGET_SEASON].copy()
    shoot = df_shoot[df_shoot["Season_End_Year"] == TARGET_SEASON].copy()
    pas   = df_pass[df_pass["Season_End_Year"] == TARGET_SEASON].copy()

    log.info("  Standard rows: %d", len(std))

    # ------------------------------------------------------------------
    # 3. Extract player_id from FBref URL
    # ------------------------------------------------------------------
    std["player_id"] = std["Url"].apply(extract_player_id)

    # ------------------------------------------------------------------
    # 4. Build core dataframe from standard stats
    # ------------------------------------------------------------------
    merge_keys = ["Season_End_Year", "Squad", "Player", "Pos"]

    core = std[[
        "player_id", "Player", "Pos", "Age", "Squad", "Comp",
        "Min_Playing", "Gls", "Ast",
        "xG_Expected", "xAG_Expected",
        "Mins_Per_90_Playing",
    ]].copy()

    core.columns = [
        "player_id", "name", "_pos_raw", "age", "club", "league",
        "minutes_played", "goals", "assists",
        "xg", "xa",
        "mins_per_90",
    ]

    # ------------------------------------------------------------------
    # 5. Merge shots from shooting stats
    # ------------------------------------------------------------------
    shoot_slim = shoot[merge_keys + ["Sh_Standard"]].copy()
    shoot_slim.columns = ["season", "club_s", "name", "_pos_raw", "shots"]
    shoot_slim = shoot_slim.drop(columns=["season", "club_s", "_pos_raw"])
    # Merge on name only (Squad may differ slightly); drop duplicates first
    shoot_slim = shoot_slim.drop_duplicates(subset=["name"], keep="first")
    core = core.merge(shoot_slim, on="name", how="left")

    # ------------------------------------------------------------------
    # 6. Merge total passes attempted from passing stats
    # ------------------------------------------------------------------
    pass_slim = pas[merge_keys + ["Att_Total"]].copy()
    pass_slim.columns = ["season", "club_p", "name", "_pos_raw", "passes"]
    pass_slim = pass_slim.drop(columns=["season", "club_p", "_pos_raw"])
    pass_slim = pass_slim.drop_duplicates(subset=["name"], keep="first")
    core = core.merge(pass_slim, on="name", how="left")

    # ------------------------------------------------------------------
    # 7. Normalise position
    # ------------------------------------------------------------------
    core["position"] = core["_pos_raw"].apply(normalise_position)
    core.drop(columns=["_pos_raw"], inplace=True)

    # ------------------------------------------------------------------
    # 8. Normalise league names
    # ------------------------------------------------------------------
    core["league"] = core["league"].map(LEAGUE_CLEAN).fillna(core["league"])

    # ------------------------------------------------------------------
    # 9. Coerce numeric columns, fill missing with 0
    # ------------------------------------------------------------------
    numeric_cols = ["minutes_played", "goals", "assists", "xg", "xa",
                    "shots", "passes", "mins_per_90", "age"]
    for col in numeric_cols:
        core[col] = pd.to_numeric(core[col], errors="coerce").fillna(0)

    core["age"]          = core["age"].astype(int)
    core["goals"]        = core["goals"].astype(int)
    core["assists"]      = core["assists"].astype(int)
    core["minutes_played"] = core["minutes_played"].astype(int)
    core["shots"]        = core["shots"].fillna(0).astype(int)
    core["passes"]       = core["passes"].fillna(0).astype(int)
    core["xg"]           = core["xg"].round(2)
    core["xa"]           = core["xa"].round(2)

    # ------------------------------------------------------------------
    # 10. Filter: keep only players with >= 90 minutes
    # ------------------------------------------------------------------
    before = len(core)
    core = core[core["minutes_played"] >= 90].copy()
    log.info("Filtered %d -> %d players (>=90 min)", before, len(core))

    # Drop rows with missing name, position, club, league
    core.dropna(subset=["name", "position", "club", "league"], inplace=True)

    # Drop rows where age == 0 (FBref data anomalies / missing birth year entries)
    before_age = len(core)
    core = core[core["age"] > 0].copy()
    log.info("Dropped %d rows with age=0 (FBref anomalies)", before_age - len(core))

    # ------------------------------------------------------------------
    # 11. Compute market value estimate (deterministic tier + league mult)
    # ------------------------------------------------------------------
    log.info("Computing market value estimates...")

    # Precompute performance score thresholds per position
    thresholds: dict[str, tuple] = {}
    for pos in ["GK", "DEF", "MID", "FWD"]:
        sub = core[core["position"] == pos]
        if len(sub) < 5:
            thresholds[pos] = (0.05, 0.20, 0.40)
            continue
        p90 = sub["mins_per_90"].clip(lower=1)
        scores = (sub["xg"] + sub["xa"]) / p90
        thresholds[pos] = (
            float(scores.quantile(0.25)),
            float(scores.quantile(0.75)),
            float(scores.quantile(0.90)),
        )
        log.info("  %s thresholds (q25/q75/q90): %.3f / %.3f / %.3f", pos, *thresholds[pos])

    core["market_value_eur"] = core.apply(
        lambda row: estimate_market_value(row, thresholds), axis=1
    )

    # ------------------------------------------------------------------
    # 12. Drop helper column; reorder final columns
    # ------------------------------------------------------------------
    final_cols = [
        "player_id", "name", "position", "age", "club", "league",
        "market_value_eur", "goals", "assists", "minutes_played",
        "shots", "passes", "xg", "xa",
    ]
    core = core[final_cols]

    # ------------------------------------------------------------------
    # 13. Save
    # ------------------------------------------------------------------
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    core.to_csv(OUTPUT_PATH, index=False)
    log.info("Saved %d rows to %s", len(core), OUTPUT_PATH)

    # ------------------------------------------------------------------
    # 14. Summary report
    # ------------------------------------------------------------------
    log.info("\n=== BUILD SUMMARY ===")
    log.info("Season: 2021-22 (season_end_year=%d)", TARGET_SEASON)
    log.info("Total players: %d", len(core))
    log.info("")
    log.info("Per-league breakdown:")
    print(core.groupby("league")["player_id"].count().to_string())
    log.info("")
    log.info("Per-position breakdown:")
    print(core.groupby("position")["player_id"].count().to_string())
    log.info("")
    log.info("Null counts:")
    print(core.isnull().sum().to_string())
    log.info("")
    log.info("xA coverage: %.1f%% non-zero", (core["xa"] > 0).mean() * 100)
    log.info("xA null:     %d / %d", core["xa"].isna().sum(), len(core))
    log.info("Age range:   %d – %d", core["age"].min(), core["age"].max())
    log.info("MV range:    €%s – €%s",
             f"{core['market_value_eur'].min():,}",
             f"{core['market_value_eur'].max():,}")
    log.info("")
    log.info("Sample rows:")
    print(core[["name","position","age","club","league","goals","assists",
                "xg","xa","market_value_eur"]].head(8).to_string())


if __name__ == "__main__":
    main()
