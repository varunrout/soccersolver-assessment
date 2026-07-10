"""
tests/test_comparison_service.py — unit tests for comparison_service.

Run from backend/:
    pytest
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _clear_caches() -> None:
    from services.data_service import _load_df
    _load_df.cache_clear()


@pytest.fixture(autouse=True)
def clear_caches_around_test():
    _clear_caches()
    yield
    _clear_caches()


_HEADER = [
    "player_id", "name", "position", "age", "club", "league",
    "market_value_eur", "goals", "assists", "minutes_played",
    "shots", "passes", "xg", "xa",
]


def _write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "players_test.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return p


def _row(**kwargs) -> dict:
    base = {
        "player_id": "p1", "name": "Test Player", "position": "FWD",
        "age": "25", "club": "TestFC", "league": "Premier League",
        "market_value_eur": "10000000", "goals": "10", "assists": "5",
        "minutes_played": "1800", "shots": "50", "passes": "300",
        "xg": "8.0", "xa": "4.0",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Known real players used across tests
# Salah: e342ad68, Harry Kane: 21a66f6a (both PL FWDs)
# ---------------------------------------------------------------------------

SALAH_ID = "e342ad68"
KANE_ID  = "21a66f6a"


# ---------------------------------------------------------------------------
# compare_players — basic contract
# ---------------------------------------------------------------------------

class TestComparePlayers:

    def test_two_known_players_returns_result(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None

    def test_unknown_player_a_returns_none(self):
        from services.comparison_service import compare_players
        result = compare_players("does-not-exist", KANE_ID)
        assert result is None

    def test_unknown_player_b_returns_none(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, "does-not-exist")
        assert result is None

    def test_both_unknown_returns_none(self):
        from services.comparison_service import compare_players
        result = compare_players("ghost-a", "ghost-b")
        assert result is None

    def test_result_includes_player_a(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        assert result.player_a.player_id == SALAH_ID

    def test_result_includes_player_b(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        assert result.player_b.player_id == KANE_ID

    def test_result_has_six_metrics(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        assert len(result.metrics) == 6

    def test_metric_names(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        names = {m.metric_name for m in result.metrics}
        assert names == {
            "goals_p90", "assists_p90", "shots_p90",
            "passes_p90", "xg_p90", "xa_p90",
        }

    def test_winner_is_valid_value(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        for m in result.metrics:
            assert m.winner in ("a", "b", "draw")

    def test_winner_consistent_with_values(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        for m in result.metrics:
            if m.value_a > m.value_b:
                assert m.winner == "a"
            elif m.value_b > m.value_a:
                assert m.winner == "b"
            else:
                assert m.winner == "draw"

    def test_metric_values_non_negative(self):
        from services.comparison_service import compare_players
        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        for m in result.metrics:
            assert m.value_a >= 0.0
            assert m.value_b >= 0.0


# ---------------------------------------------------------------------------
# Draw logic
# ---------------------------------------------------------------------------

class TestDrawLogic:

    def test_draw_when_equal_values(self, tmp_path, monkeypatch):
        """Two players with identical stats must produce 'draw' on every metric."""
        import os
        from services.comparison_service import compare_players

        row_a = _row(player_id="pa", name="Player A", goals="10", assists="5",
                     minutes_played="1800", shots="50", passes="400",
                     xg="8.0", xa="4.0")
        row_b = _row(player_id="pb", name="Player B", goals="10", assists="5",
                     minutes_played="1800", shots="50", passes="400",
                     xg="8.0", xa="4.0")
        csv_path = _write_csv(tmp_path, [row_a, row_b])
        monkeypatch.setenv("CSV_PATH", str(csv_path))

        result = compare_players("pa", "pb")
        assert result is not None
        for m in result.metrics:
            assert m.winner == "draw", f"{m.metric_name} should be draw"

    def test_draw_after_rounding(self, tmp_path, monkeypatch):
        """Values that differ only past P90_ROUND decimals must round to draw."""
        from services.comparison_service import compare_players

        # 9.0/1800*90 = 0.450000 vs 9.0000001/1800*90 ≈ 0.450000005 → same after round 3
        row_a = _row(player_id="pa", name="Player A", goals="9.0",
                     minutes_played="1800")
        row_b = _row(player_id="pb", name="Player B", goals="9.0000001",
                     minutes_played="1800")
        csv_path = _write_csv(tmp_path, [row_a, row_b])
        monkeypatch.setenv("CSV_PATH", str(csv_path))

        result = compare_players("pa", "pb")
        assert result is not None
        goals_cmp = next(m for m in result.metrics if m.metric_name == "goals_p90")
        assert goals_cmp.winner == "draw"


# ---------------------------------------------------------------------------
# Zero-minute player
# ---------------------------------------------------------------------------

class TestZeroMinutePlayer:

    def test_zero_minutes_does_not_crash(self, tmp_path, monkeypatch):
        from services.comparison_service import compare_players

        row_a = _row(player_id="pa", name="Active", minutes_played="1800",
                     goals="10", assists="5", shots="40", passes="300",
                     xg="8.0", xa="3.0")
        row_b = _row(player_id="pb", name="Inactive", minutes_played="0",
                     goals="0", assists="0", shots="0", passes="0",
                     xg="0.0", xa="0.0")
        csv_path = _write_csv(tmp_path, [row_a, row_b])
        monkeypatch.setenv("CSV_PATH", str(csv_path))

        result = compare_players("pa", "pb")
        assert result is not None

    def test_zero_minutes_yields_zero_values(self, tmp_path, monkeypatch):
        from services.comparison_service import compare_players

        row_a = _row(player_id="pa", name="Active", minutes_played="1800",
                     goals="10", assists="5", shots="40", passes="300",
                     xg="8.0", xa="3.0")
        row_b = _row(player_id="pb", name="Inactive", minutes_played="0",
                     goals="0", assists="0", shots="0", passes="0",
                     xg="0.0", xa="0.0")
        csv_path = _write_csv(tmp_path, [row_a, row_b])
        monkeypatch.setenv("CSV_PATH", str(csv_path))

        result = compare_players("pa", "pb")
        assert result is not None
        for m in result.metrics:
            assert m.value_b == 0.0

    def test_zero_minutes_both_are_draw(self, tmp_path, monkeypatch):
        from services.comparison_service import compare_players

        row_a = _row(player_id="pa", name="Bench A", minutes_played="0",
                     goals="0", assists="0", shots="0", passes="0",
                     xg="0.0", xa="0.0")
        row_b = _row(player_id="pb", name="Bench B", minutes_played="0",
                     goals="0", assists="0", shots="0", passes="0",
                     xg="0.0", xa="0.0")
        csv_path = _write_csv(tmp_path, [row_a, row_b])
        monkeypatch.setenv("CSV_PATH", str(csv_path))

        result = compare_players("pa", "pb")
        assert result is not None
        for m in result.metrics:
            assert m.winner == "draw"


# ---------------------------------------------------------------------------
# Market context
# ---------------------------------------------------------------------------

class TestMarketContext:

    def test_market_context_contains_player_values(self):
        from services.comparison_service import compare_players
        from services.data_service import get_player_by_id

        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        salah = get_player_by_id(SALAH_ID)
        kane  = get_player_by_id(KANE_ID)
        assert result.market_context.value_a == salah.market_value_eur
        assert result.market_context.value_b == kane.market_value_eur

    def test_market_averages_are_int_or_none(self):
        from services.comparison_service import compare_players

        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        avg_a = result.market_context.league_avg_a
        avg_b = result.market_context.league_avg_b
        assert avg_a is None or isinstance(avg_a, int)
        assert avg_b is None or isinstance(avg_b, int)

    def test_market_averages_non_negative(self):
        from services.comparison_service import compare_players

        result = compare_players(SALAH_ID, KANE_ID)
        assert result is not None
        if result.market_context.league_avg_a is not None:
            assert result.market_context.league_avg_a >= 0
        if result.market_context.league_avg_b is not None:
            assert result.market_context.league_avg_b >= 0

    def test_market_avg_none_when_no_peers(self, tmp_path, monkeypatch):
        """league_avg_a/b is None when all same-position+league players have < min_minutes."""
        from services.comparison_service import compare_players

        # pa and pb are the only players in their respective leagues,
        # but with 0 minutes they fall below the DEFAULT_MIN_MINUTES threshold,
        # so the peer group returned by get_players(min_minutes=300) is empty.
        row_a = _row(player_id="pa", name="Lonely A", position="FWD",
                     league="Niche League", market_value_eur="5000000",
                     minutes_played="0")
        row_b = _row(player_id="pb", name="Lonely B", position="DEF",
                     league="Other League", market_value_eur="3000000",
                     minutes_played="0")
        csv_path = _write_csv(tmp_path, [row_a, row_b])
        monkeypatch.setenv("CSV_PATH", str(csv_path))

        result = compare_players("pa", "pb")
        assert result is not None
        assert result.market_context.league_avg_a is None
        assert result.market_context.league_avg_b is None


# ---------------------------------------------------------------------------
# _metric_winner helper
# ---------------------------------------------------------------------------

class TestMetricWinner:

    def test_a_wins(self):
        from services.comparison_service import _metric_winner
        assert _metric_winner(0.6, 0.4) == "a"

    def test_b_wins(self):
        from services.comparison_service import _metric_winner
        assert _metric_winner(0.3, 0.5) == "b"

    def test_draw(self):
        from services.comparison_service import _metric_winner
        assert _metric_winner(0.5, 0.5) == "draw"

    def test_zero_both(self):
        from services.comparison_service import _metric_winner
        assert _metric_winner(0.0, 0.0) == "draw"


# ---------------------------------------------------------------------------
# _average_market_value helper
# ---------------------------------------------------------------------------

class TestAverageMarketValue:

    def test_returns_int(self):
        from services.comparison_service import _average_market_value
        avg = _average_market_value("FWD", "Premier League")
        assert avg is None or isinstance(avg, int)

    def test_returns_none_for_empty_peer_group(self):
        from services.comparison_service import _average_market_value
        avg = _average_market_value("FWD", "NonExistentLeague")
        assert avg is None

    def test_custom_csv_average(self, tmp_path, monkeypatch):
        from services.comparison_service import _average_market_value

        rows = [
            _row(player_id="p1", name="A", position="MID", league="Liga Test",
                 market_value_eur="10000000", minutes_played="900"),
            _row(player_id="p2", name="B", position="MID", league="Liga Test",
                 market_value_eur="20000000", minutes_played="900"),
            _row(player_id="p3", name="C", position="FWD", league="Liga Test",
                 market_value_eur="99000000", minutes_played="900"),
        ]
        csv_path = _write_csv(tmp_path, rows)
        monkeypatch.setenv("CSV_PATH", str(csv_path))

        avg = _average_market_value("MID", "Liga Test", min_minutes=300)
        assert avg == 15_000_000  # (10M + 20M) / 2


# ---------------------------------------------------------------------------
# No direct CSV access
# ---------------------------------------------------------------------------

class TestNoCsvDirectRead:

    def test_no_pandas_read_in_comparison_service(self):
        """comparison_service must not import or call pd.read_csv directly."""
        import ast
        import inspect
        import services.comparison_service as svc

        source = inspect.getsource(svc)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in ("pandas", "csv"), (
                            f"comparison_service imports '{alias.name}' directly"
                        )
                else:
                    assert node.module not in ("pandas", "csv"), (
                        f"comparison_service imports from '{node.module}' directly"
                    )
