"""
tests/test_data_service.py — unit tests for the CSV data access layer.

Run from backend/:
    pytest
"""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_cache() -> None:
    """Clear the lru_cache so each test gets a fresh load."""
    from services import data_service
    data_service._load_df.cache_clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache_around_test():
    """Ensure tests don't share cached DataFrames."""
    _clear_cache()
    yield
    _clear_cache()


@pytest.fixture()
def tmp_csv(tmp_path: Path):
    """
    Factory fixture: call tmp_csv(rows) to get a Path to a temporary CSV
    containing the required columns plus the supplied data rows.
    """
    header = [
        "player_id", "name", "position", "age", "club", "league",
        "market_value_eur", "goals", "assists", "minutes_played",
        "shots", "passes", "xg", "xa",
    ]

    def _make(rows: list[dict]) -> Path:
        p = tmp_path / "players_test.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
        return p

    return _make


def _two_players():
    return [
        {
            "player_id": "aaa111", "name": "Alice Smith", "position": "FWD",
            "age": 25, "club": "Arsenal", "league": "Premier League",
            "market_value_eur": 20000000, "goals": 15, "assists": 5,
            "minutes_played": 2700, "shots": 80, "passes": 500,
            "xg": 14.2, "xa": 4.8,
        },
        {
            "player_id": "bbb222", "name": "Bob Jones", "position": "MID",
            "age": 28, "club": "Chelsea", "league": "Premier League",
            "market_value_eur": 15000000, "goals": 5, "assists": 10,
            "minutes_played": 3000, "shots": 40, "passes": 1200,
            "xg": 4.5, "xa": 9.1,
        },
    ]


# ---------------------------------------------------------------------------
# Load tests
# ---------------------------------------------------------------------------

class TestLoad:
    def test_real_csv_loads(self):
        """The production players.csv loads without error."""
        from services.data_service import _load_df
        df = _load_df()
        assert len(df) > 0
        assert "player_id" in df.columns

    def test_real_csv_row_count(self):
        from services.data_service import _load_df
        df = _load_df()
        assert len(df) >= 2000, f"Expected 2000+ rows, got {len(df)}"

    def test_real_csv_no_null_player_ids(self):
        from services.data_service import _load_df
        df = _load_df()
        assert df["player_id"].eq("").sum() == 0

    def test_real_csv_player_ids_unique(self):
        from services.data_service import _load_df
        df = _load_df()
        assert not df["player_id"].duplicated().any()

    def test_real_csv_numeric_columns_valid(self):
        from services.data_service import _load_df
        df = _load_df()
        for col in ["goals", "assists", "minutes_played", "shots", "passes"]:
            assert df[col].ge(0).all(), f"{col} has negative values"
        for col in ["xg", "xa"]:
            assert df[col].ge(0).all(), f"{col} has negative values"

    def test_missing_column_raises(self, tmp_path, monkeypatch):
        """A CSV missing a required column raises ValueError."""
        import csv as _csv
        p = tmp_path / "bad.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=["player_id", "name"])
            writer.writeheader()
            writer.writerow({"player_id": "x1", "name": "Test"})

        monkeypatch.setenv("CSV_PATH", str(p))
        from services import data_service
        data_service._load_df.cache_clear()

        with pytest.raises(ValueError, match="missing required columns"):
            data_service._load_df()

    def test_duplicate_player_id_raises(self, tmp_csv, monkeypatch):
        """A CSV with duplicate player_ids raises ValueError."""
        rows = _two_players()
        rows[1]["player_id"] = rows[0]["player_id"]   # force duplicate
        p = tmp_csv(rows)

        monkeypatch.setenv("CSV_PATH", str(p))
        from services import data_service
        data_service._load_df.cache_clear()

        with pytest.raises(ValueError, match="duplicate player_id"):
            data_service._load_df()

    def test_custom_csv_path_via_env(self, tmp_csv, monkeypatch):
        """CSV_PATH env var is respected."""
        p = tmp_csv(_two_players())
        monkeypatch.setenv("CSV_PATH", str(p))
        from services import data_service
        data_service._load_df.cache_clear()

        df = data_service._load_df()
        assert len(df) == 2

    def test_missing_file_raises(self, monkeypatch):
        """A non-existent path raises FileNotFoundError."""
        monkeypatch.setenv("CSV_PATH", "/nonexistent/path/players.csv")
        from services import data_service
        data_service._load_df.cache_clear()

        with pytest.raises(FileNotFoundError):
            data_service._load_df()


# ---------------------------------------------------------------------------
# search_players tests
# ---------------------------------------------------------------------------

class TestSearchPlayers:
    def test_known_player_found(self):
        """Salah is in the dataset and search returns him."""
        from services.data_service import search_players
        results = search_players("Salah")
        names = [p.name for p in results]
        assert any("Salah" in n for n in names), f"Salah not found in {names}"

    def test_empty_query_returns_empty(self):
        from services.data_service import search_players
        assert search_players("") == []
        assert search_players("   ") == []

    def test_case_insensitive(self):
        from services.data_service import search_players
        lower = search_players("salah")
        upper = search_players("SALAH")
        assert len(lower) > 0
        assert {p.player_id for p in lower} == {p.player_id for p in upper}

    def test_returns_player_summary_objects(self):
        from services.data_service import search_players
        from models.player import PlayerSummary
        results = search_players("Smith")
        for r in results:
            assert isinstance(r, PlayerSummary)

    def test_max_results_respected(self):
        from services.data_service import search_players, SEARCH_LIMIT
        # 'a' should match many players; result must be capped
        results = search_players("a")
        assert len(results) <= SEARCH_LIMIT

    def test_no_match_returns_empty(self):
        from services.data_service import search_players
        results = search_players("ZZZNOSUCHWXYZ")
        assert results == []

    def test_exact_match_first(self, tmp_csv, monkeypatch):
        """Exact name match should appear before prefix/contains matches."""
        rows = _two_players()
        rows[0]["name"] = "Ali"
        rows[1]["name"] = "Alice Smith"
        p = tmp_csv(rows)
        monkeypatch.setenv("CSV_PATH", str(p))
        from services import data_service
        data_service._load_df.cache_clear()

        results = data_service.search_players("Ali")
        assert results[0].name == "Ali"

    def test_prefix_before_substring(self, tmp_csv, monkeypatch):
        """Prefix match should outrank mid-name contains."""
        rows = _two_players()
        rows[0]["name"] = "John Smith"   # "smith" is a substring, not a prefix
        rows[1]["name"] = "Smithson"     # starts with "Smith"
        rows[0]["minutes_played"] = 9999  # give substring-match more minutes (should still lose)
        p = tmp_csv(rows)
        monkeypatch.setenv("CSV_PATH", str(p))
        from services import data_service
        data_service._load_df.cache_clear()

        results = data_service.search_players("Smith")
        assert results[0].name == "Smithson"


# ---------------------------------------------------------------------------
# get_player_by_id tests
# ---------------------------------------------------------------------------

class TestGetPlayerById:
    def test_known_player_returned(self):
        """e342ad68 is Mohamed Salah's player_id in the dataset."""
        from services.data_service import get_player_by_id
        from models.player import PlayerDetail
        player = get_player_by_id("e342ad68")
        assert player is not None
        assert isinstance(player, PlayerDetail)
        assert "Salah" in player.name

    def test_returns_correct_stats(self):
        from services.data_service import get_player_by_id
        player = get_player_by_id("e342ad68")
        assert player is not None
        assert player.goals >= 0
        assert player.minutes_played > 0

    def test_unknown_id_returns_none(self):
        from services.data_service import get_player_by_id
        assert get_player_by_id("this-id-does-not-exist") is None

    def test_returns_player_detail(self, tmp_csv, monkeypatch):
        p = tmp_csv(_two_players())
        monkeypatch.setenv("CSV_PATH", str(p))
        from services import data_service
        data_service._load_df.cache_clear()

        result = data_service.get_player_by_id("aaa111")
        assert result is not None
        assert result.name == "Alice Smith"
        assert result.goals == 15
        assert result.xg == pytest.approx(14.2)


# ---------------------------------------------------------------------------
# get_players tests
# ---------------------------------------------------------------------------

class TestGetPlayers:
    def test_returns_all_without_filters(self):
        from services.data_service import get_players, _load_df
        all_players = get_players()
        df = _load_df()
        assert len(all_players) == len(df)

    def test_filter_by_position(self):
        from services.data_service import get_players
        fwds = get_players(position="FWD")
        assert len(fwds) > 0
        assert all(p.position == "FWD" for p in fwds)

    def test_filter_by_league(self):
        from services.data_service import get_players
        pl = get_players(league="Premier League")
        assert len(pl) > 0
        assert all(p.league == "Premier League" for p in pl)

    def test_filter_by_min_minutes(self):
        from services.data_service import get_players
        results = get_players(min_minutes=2000)
        assert len(results) > 0
        assert all(p.minutes_played >= 2000 for p in results)

    def test_combined_filters(self):
        from services.data_service import get_players
        results = get_players(position="MID", league="La Liga", min_minutes=1000)
        assert all(p.position == "MID" for p in results)
        assert all(p.league == "La Liga" for p in results)
        assert all(p.minutes_played >= 1000 for p in results)

    def test_sorted_by_minutes_desc(self):
        from services.data_service import get_players
        results = get_players(league="Premier League")
        minutes = [p.minutes_played for p in results]
        assert minutes == sorted(minutes, reverse=True)

    def test_case_insensitive_filters(self):
        from services.data_service import get_players
        upper = get_players(position="FWD", league="PREMIER LEAGUE")
        lower = get_players(position="fwd", league="premier league")
        assert {p.player_id for p in upper} == {p.player_id for p in lower}

    def test_impossible_filter_returns_empty(self):
        from services.data_service import get_players
        results = get_players(position="FWD", min_minutes=99999)
        assert results == []

    def test_returns_player_detail_objects(self):
        from services.data_service import get_players
        from models.player import PlayerDetail
        results = get_players(league="Serie A", min_minutes=500)
        assert len(results) > 0
        for p in results:
            assert isinstance(p, PlayerDetail)

    def test_custom_csv_filters(self, tmp_csv, monkeypatch):
        p = tmp_csv(_two_players())
        monkeypatch.setenv("CSV_PATH", str(p))
        from services import data_service
        data_service._load_df.cache_clear()

        fwds = data_service.get_players(position="FWD")
        assert len(fwds) == 1
        assert fwds[0].name == "Alice Smith"

        pl = data_service.get_players(league="Premier League")
        assert len(pl) == 2

        high_min = data_service.get_players(min_minutes=2800)
        assert len(high_min) == 1
        assert high_min[0].name == "Bob Jones"
