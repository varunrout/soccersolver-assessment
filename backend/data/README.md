# Data Directory — SoccerSolver Assessment

## Dataset: FBref Big 5 European Leagues — Season 2021-22

### Source
Pre-compiled FBref player season statistics from the
[worldfootballR_data](https://github.com/JaseZiv/worldfootballR_data) GitHub
repository (R `.rds` files, read via `pyreadr`).

Original data provider: **FBref / Sports Reference LLC**
(https://fbref.com)

License / use assumption: Data is used for educational and non-commercial
purposes only, consistent with FBref's terms of service. The worldfootballR_data
repository is a public mirror intended for research use.

---

### How to regenerate

```bash
pip install requests pyreadr pandas
python backend/scripts/build_dataset.py
```

The script downloads three `.rds` files from GitHub (~5 MB total) and outputs
`players.csv` in under 10 seconds.

---

### Leagues and season included

| League | Season | Players |
|---|---|---|
| Premier League | 2021-22 | 488 |
| La Liga | 2021-22 | 546 |
| Serie A | 2021-22 | 531 |
| Bundesliga | 2021-22 | 449 |
| Ligue 1 | 2021-22 | 512 |
| **Total** | | **2,526** |

---

### Columns

| Column | Source | Notes |
|---|---|---|
| `player_id` | FBref | Extracted from FBref player URL hash (e.g. `39168d69`). **Unique per row** — mid-season transfers are aggregated into one season-total row. |
| `name` | FBref | Real player name |
| `position` | FBref | Normalised: `GK`, `DEF`, `MID`, `FWD`. FBref's primary position tag used when a player has multiple (e.g. `MF,FW` → `MID`) |
| `age` | FBref | **Real age** as of the start of the 2021-22 season |
| `club` | FBref | Club name as used by FBref |
| `league` | FBref | One of: Premier League, La Liga, Serie A, Bundesliga, Ligue 1 |
| `market_value_eur` | **Estimated** | See section below |
| `goals` | FBref | Non-penalty goals in league season |
| `assists` | FBref | Goal assists in league season |
| `minutes_played` | FBref | Total minutes played in league season |
| `shots` | FBref | Total shots (including blocked) |
| `passes` | FBref | Total passes attempted |
| `xg` | FBref | Expected Goals (npxG) — real FBref model |
| `xa` | FBref | Expected Assists (xAG) — real FBref model |

---

### Transformations applied

1. Filter: only seasons with `season_end_year == 2022` (2021-22 season)
2. Filter: players with `minutes_played >= 90` only (removes statistical noise from cameo appearances)
3. Position normalisation: FBref primary position tag mapped to `GK / DEF / MID / FWD`
4. Numeric coercion: all metric columns cast to float/int; remaining NaN filled with `0`
5. **Strong 4-key merge**: shots (from `big5_player_shooting.rds`) and passes (from `big5_player_passing.rds`) are merged on `Season_End_Year + Squad + Comp + Player` — not on player name alone — to avoid misassignment for duplicate names or transferred players
6. **Transfer aggregation**: players who transferred mid-season appear once per club in FBref. These rows are aggregated into a single season-total row: counting stats (goals, assists, shots, passes, xg, xa, minutes) are **summed**; the club/league where the player had the most minutes is used as the canonical value. This ensures `player_id` is unique in the final CSV.
7. Drop rows with `age == 0` (FBref anomaly entries where birth year is missing)

---

### Known limitations

#### Market value (`market_value_eur`) — ESTIMATED, not real
Real Transfermarkt market values are not available from any free, API-accessible
source without scraping. `market_value_eur` is a **tier-based deterministic
estimate** computed as follows:

```
tier = performance quartile within position
       (based on (xG + xA) / mins_per_90)

base_value = position × tier lookup table
             (GK: €1M–€22M | DEF: €1.5M–€35M | MID: €2M–€45M | FWD: €2.5M–€65M)

market_value_eur = base_value × league_prestige_multiplier
                   (PL ×1.6 | La Liga ×1.4 | BL ×1.3 | SA ×1.2 | L1 ×1.1)
```

**No random noise is applied.** Values are deterministic and reproducible.
All downstream code and the README must treat `market_value_eur` as an
approximation, not a real market figure.

#### xA (`xa`) — real but partially zero for low-activity players
`xa` (xAG from FBref) is a real expected-assists metric from the FBref model.
Coverage: **84.8% of players have xA > 0**. Players with `xa == 0` genuinely
had zero expected assists in the season (e.g. goalkeepers, bench players with
few passes into dangerous areas). This is not a data gap — it reflects real
playing data.

#### Age edge cases
Rows with `age == 0` in the FBref source (data entry anomalies where a player's
birth year is missing) are **filtered out** during the build step. No `age == 0`
rows exist in the final CSV.

#### Shots and passes join quality
Shots and passes are merged on `Season_End_Year + Squad + Comp + Player` (4-key join) from separate FBref tables. This is a strong join that correctly handles duplicate player names and mid-season transfers. After the join, transferred players are aggregated before writing the final CSV.

---

### Validation

Run before using the data:

```bash
python backend/scripts/validate_dataset.py
```
