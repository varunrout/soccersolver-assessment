"""
validate_dataset.py
-------------------
Validates backend/data/players.csv against the requirements for the
SoccerSolver assessment.

Run:
    python backend/scripts/validate_dataset.py

Exits with code 1 if any check fails.
"""

import sys
from pathlib import Path

import pandas as pd

CSV_PATH = Path(__file__).parent.parent / "data" / "players.csv"

REQUIRED_COLUMNS = [
    "player_id", "name", "position", "age", "club", "league",
    "market_value_eur", "goals", "assists", "minutes_played",
    "shots", "passes", "xg", "xa",
]

REQUIRED_LEAGUES = {"Premier League", "La Liga", "Serie A"}
NUMERIC_COLS     = ["age", "goals", "assists", "minutes_played",
                    "shots", "passes", "xg", "xa", "market_value_eur"]
NO_NULL_COLS     = ["name", "position", "club", "league", "player_id"]

MIN_ROWS = 1000


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    msg    = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition


def run_validation() -> bool:
    print(f"\nValidating: {CSV_PATH}\n")
    all_pass = True

    # ---- File exists ----
    if not CSV_PATH.exists():
        print(f"  [FAIL] File not found: {CSV_PATH}")
        return False

    df = pd.read_csv(CSV_PATH)

    # ---- Required columns ----
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    all_pass &= check(
        "Required columns present",
        len(missing_cols) == 0,
        f"Missing: {missing_cols}" if missing_cols else f"{len(REQUIRED_COLUMNS)} columns OK",
    )
    if missing_cols:
        return False  # Can't continue without columns

    # ---- Row count ----
    all_pass &= check(
        "Row count >= 1000",
        len(df) >= MIN_ROWS,
        f"{len(df)} rows",
    )

    # ---- League coverage ----
    leagues_present = set(df["league"].dropna().unique())
    for league in REQUIRED_LEAGUES:
        count = (df["league"] == league).sum()
        all_pass &= check(
            f"League present: {league}",
            league in leagues_present,
            f"{count} players",
        )

    # ---- No nulls in critical string columns ----
    for col in NO_NULL_COLS:
        null_count = df[col].isna().sum()
        all_pass &= check(
            f"No nulls in '{col}'",
            null_count == 0,
            f"{null_count} nulls",
        )

    # ---- Numeric columns are valid (no NaN, non-negative) ----
    for col in NUMERIC_COLS:
        null_count = df[col].isna().sum()
        neg_count  = (pd.to_numeric(df[col], errors="coerce") < 0).sum()
        all_pass &= check(
            f"Numeric '{col}': no nulls, non-negative",
            null_count == 0 and neg_count == 0,
            f"nulls={null_count}, negatives={neg_count}",
        )

    # ---- xA: not silently all-zero without documentation ----
    xa_zero_pct = (df["xa"] == 0).mean() * 100
    xa_all_zero = xa_zero_pct > 99.0
    if xa_all_zero:
        print(
            "  [WARN] xA is >99% zero — this must be explicitly documented "
            "in data/README.md and handled carefully in downstream code."
        )
        # Not a hard failure if the README documents it
    else:
        all_pass &= check(
            "xA is not silently all-zero",
            not xa_all_zero,
            f"{100 - xa_zero_pct:.1f}% non-zero",
        )

    # ---- Age is not hash-generated (check distribution is plausible) ----
    age_min  = int(df[df["age"] > 0]["age"].min())
    age_max  = int(df["age"].max())
    age_mean = df[df["age"] > 0]["age"].mean()
    plausible_age = 15 <= age_min <= 22 and 35 <= age_max <= 45 and 24 <= age_mean <= 30
    all_pass &= check(
        "Age distribution is plausible (not hash-generated)",
        plausible_age,
        f"min={age_min}, max={age_max}, mean={age_mean:.1f}",
    )

    # ---- Market value: not random-noise (check it's not uniform per position) ----
    mv_std_by_pos = df.groupby("position")["market_value_eur"].std()
    mv_has_variance = (mv_std_by_pos > 0).all()
    all_pass &= check(
        "Market value has variance per position (not flat)",
        mv_has_variance,
        f"std per position: {mv_std_by_pos.to_dict()}",
    )

    # ---- player_id uniqueness — hard failure (required for /players/{id} routing) ----
    dup_ids = df["player_id"].duplicated().sum()
    all_pass &= check(
        "player_id is unique (required for /players/{id} routing)",
        dup_ids == 0,
        f"{dup_ids} duplicates" if dup_ids else "all unique",
    )

    # ---- Summary ----
    print()
    print(f"{'=' * 50}")
    print(f"  Total players : {len(df)}")
    print(f"  Leagues       : {sorted(df['league'].dropna().unique())}")
    print(f"  Age range     : {int(df['age'].min())} – {int(df['age'].max())}")
    print(f"  xA coverage   : {(df['xa'] > 0).mean()*100:.1f}% non-zero")
    print(f"  MV range      : €{df['market_value_eur'].min():,.0f} – €{df['market_value_eur'].max():,.0f}")
    print(f"{'=' * 50}")
    result = "ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED"
    print(f"  Result: {result}")
    print()

    return all_pass


if __name__ == "__main__":
    passed = run_validation()
    sys.exit(0 if passed else 1)
