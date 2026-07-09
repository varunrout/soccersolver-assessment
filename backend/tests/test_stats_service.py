"""
tests/test_stats_service.py — unit tests for stats_service.

Run from backend/:
    pytest
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_caches() -> None:
    from services.data_service import _load_df
    _load_df.cache_clear()


@pytest.fixture(autouse=True)
def clear_caches_around_test():
    _clear_caches()
    yield
    _clear_caches()


_BASE_ROW: dict = {
    "player_id": "p1",
    "name": "Alpha Player",
    "position": "FWD",
    "age": "25",
    "club": "TestFC",
    "league": "Premier League",
    "market_value_eur": "20000000",
    "goals": "20",
    "assists": "5",
    "minutes_played": "2700",
    "shots": "90",
    "passes": "400",
    "xg": "18.0",
    "xa": "4.5",
}

_HEADERS = list(_BASE_ROW.keys())


def _make_csv(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "players.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return p


def _patch_csv(monkeypatch, tmp_path: Path, rows: list[dict]) -> Path:
    p = _make_csv(tmp_path, rows)
    monkeypatch.setenv("CSV_PATH", str(p))
    _clear_caches()
    return p


def _row(**kwargs) -> dict:
    """Return a copy of _BASE_ROW with overrides."""
    r = dict(_BASE_ROW)
    r.update({k: str(v) for k, v in kwargs.items()})
    return r


# ---------------------------------------------------------------------------
# Per-90 calculation
# ---------------------------------------------------------------------------

class TestPer90:
    def test_basic_calculation(self):
        from services.stats_service import _per90
        result = _per90(20, 2700)
        expected = round(20 / 2700 * 90, 3)
        assert result == pytest.approx(expected)

    def test_zero_minutes_returns_none(self):
        from services.stats_service import _per90
        assert _per90(10, 0) is None

    def test_negative_minutes_returns_none(self):
        from services.stats_service import _per90
        assert _per90(10, -100) is None

    def test_zero_raw_value(self):
        from services.stats_service import _per90
        assert _per90(0, 900) == pytest.approx(0.0)

    def test_rounding(self):
        from services.stats_service import _per90, P90_ROUND
        result = _per90(7, 1234)
        assert result is not None
        # result should have at most P90_ROUND decimal places
        decimals = len(str(result).split(".")[-1]) if "." in str(result) else 0
        assert decimals <= P90_ROUND


# ---------------------------------------------------------------------------
# get_peer_group
# ---------------------------------------------------------------------------

class TestGetPeerGroup:
    def test_filters_by_position_and_league(self, tmp_path, monkeypatch):
        rows = [
            _row(player_id="f1", position="FWD", league="Premier League", minutes_played=400),
            _row(player_id="m1", position="MID", league="Premier League", minutes_played=400),
            _row(player_id="f2", position="FWD", league="La Liga", minutes_played=400),
        ]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_peer_group
        peers = get_peer_group("FWD", "Premier League")
        assert len(peers) == 1
        assert peers[0].player_id == "f1"

    def test_excludes_below_min_minutes(self, tmp_path, monkeypatch):
        rows = [
            _row(player_id="a1", position="FWD", league="Premier League", minutes_played=500),
            _row(player_id="a2", position="FWD", league="Premier League", minutes_played=100),
        ]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_peer_group
        peers = get_peer_group("FWD", "Premier League", min_minutes=300)
        assert len(peers) == 1
        assert peers[0].player_id == "a1"

    def test_empty_when_no_match(self, tmp_path, monkeypatch):
        rows = [_row(player_id="x1", position="GK", league="La Liga", minutes_played=400)]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_peer_group
        assert get_peer_group("FWD", "Premier League") == []

    def test_real_dataset_peer_group(self):
        """Real dataset has sufficient Premier League FWDs."""
        from services.stats_service import get_peer_group
        peers = get_peer_group("FWD", "Premier League")
        assert len(peers) >= MIN_PG


# ---------------------------------------------------------------------------
# Percentile calculation
# ---------------------------------------------------------------------------

MIN_PG = 5  # matches MIN_PEER_GROUP_SIZE


class TestComputePercentile:
    def test_median_player_near_50(self):
        from services.stats_service import _compute_percentile
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        pct = _compute_percentile(3.0, values)
        assert 50.0 <= pct <= 70.0  # 3 out of 5 values <= 3.0

    def test_top_player_near_100(self):
        from services.stats_service import _compute_percentile
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        pct = _compute_percentile(5.0, values)
        assert pct == 100.0

    def test_bottom_player(self):
        from services.stats_service import _compute_percentile
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        pct = _compute_percentile(1.0, values)
        assert pct == pytest.approx(20.0)

    def test_result_in_0_100(self):
        from services.stats_service import _compute_percentile
        values = list(range(1, 101))
        for v in [0.5, 50.0, 100.0, 150.0]:
            pct = _compute_percentile(v, values)
            assert 0.0 <= pct <= 100.0


# ---------------------------------------------------------------------------
# get_player_percentiles
# ---------------------------------------------------------------------------

class TestGetPlayerPercentiles:
    def test_known_player_returns_percentiles(self):
        """Salah (e342ad68) has enough FWD peers in Premier League."""
        from services.stats_service import get_player_percentiles
        result = get_player_percentiles("e342ad68")
        assert result is not None
        assert result.player_id == "e342ad68"
        for metric in ["goals_p90", "assists_p90", "xg_p90"]:
            v = result.metrics.get(metric)
            assert v is None or (0.0 <= v <= 100.0), f"{metric}={v} out of range"

    def test_unknown_player_returns_none(self):
        from services.stats_service import get_player_percentiles
        assert get_player_percentiles("does-not-exist") is None

    def test_zero_minutes_returns_none(self, tmp_path, monkeypatch):
        rows = [_row(player_id="z1", minutes_played=0)]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_player_percentiles
        assert get_player_percentiles("z1") is None

    def test_small_peer_group_returns_none_metrics(self, tmp_path, monkeypatch):
        """With fewer than MIN_PEER_GROUP_SIZE peers, all metrics are None."""
        rows = [
            _row(player_id=f"p{i}", minutes_played=500)
            for i in range(MIN_PG - 1)  # too few
        ]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_player_percentiles
        result = get_player_percentiles("p0")
        assert result is not None
        assert all(v is None for v in result.metrics.values())

    def test_sufficient_peer_group_all_values_in_range(self, tmp_path, monkeypatch):
        rows = [
            _row(player_id=f"q{i}", goals=str(i * 2), minutes_played=2700)
            for i in range(MIN_PG + 3)
        ]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_player_percentiles
        result = get_player_percentiles("q0")
        assert result is not None
        for key, val in result.metrics.items():
            assert val is None or (0.0 <= val <= 100.0), f"{key}={val}"


# ---------------------------------------------------------------------------
# get_league_averages
# ---------------------------------------------------------------------------

class TestGetLeagueAverages:
    def test_returns_all_six_metrics(self):
        from services.stats_service import get_league_averages
        avgs = get_league_averages("FWD", "Premier League")
        for m in ["goals_p90", "assists_p90", "shots_p90", "passes_p90", "xg_p90", "xa_p90"]:
            assert m in avgs

    def test_values_non_negative(self):
        from services.stats_service import get_league_averages
        avgs = get_league_averages("MID", "La Liga")
        assert all(v >= 0 for v in avgs.values())

    def test_empty_group_returns_zeros(self, tmp_path, monkeypatch):
        rows = [_row(player_id="x1", position="GK", league="La Liga", minutes_played=400)]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_league_averages
        avgs = get_league_averages("FWD", "Premier League")
        assert all(v == 0.0 for v in avgs.values())

    def test_average_is_mean(self, tmp_path, monkeypatch):
        """Two FWD players with known goals — verify goals_p90 mean is correct."""
        rows = [
            _row(player_id="a1", goals=18, minutes_played=2700),  # 18/2700*90 = 0.6
            _row(player_id="a2", goals=9,  minutes_played=2700),  # 9/2700*90  = 0.3
        ]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_league_averages
        avgs = get_league_averages("FWD", "Premier League")
        # mean = (0.6 + 0.3) / 2 = 0.45
        assert avgs["goals_p90"] == pytest.approx(0.45, abs=0.001)


# ---------------------------------------------------------------------------
# get_player_profile_stats
# ---------------------------------------------------------------------------

class TestGetPlayerProfileStats:
    def test_known_player_returns_profile(self):
        from services.stats_service import get_player_profile_stats
        from models.player import PlayerDetailWithPercentiles
        result = get_player_profile_stats("e342ad68")
        assert result is not None
        assert isinstance(result, PlayerDetailWithPercentiles)
        assert "Salah" in result.name

    def test_stats_field_correct(self):
        from services.stats_service import get_player_profile_stats
        result = get_player_profile_stats("e342ad68")
        assert result is not None
        assert result.goals >= 0
        assert result.minutes_played > 0

    def test_percentiles_present(self):
        from services.stats_service import get_player_profile_stats
        result = get_player_profile_stats("e342ad68")
        assert result is not None
        # Salah has enough PL FWD peers — percentiles should not be None
        assert result.percentiles is not None

    def test_unknown_player_returns_none(self):
        from services.stats_service import get_player_profile_stats
        assert get_player_profile_stats("no-such-player") is None

    def test_percentiles_none_when_small_group(self, tmp_path, monkeypatch):
        """Only 1 player → peer group too small → percentiles has None values."""
        rows = [_row(player_id="solo1", minutes_played=2000)]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import get_player_profile_stats
        result = get_player_profile_stats("solo1")
        assert result is not None
        if result.percentiles is not None:
            assert all(v is None for v in result.percentiles.metrics.values())


# ---------------------------------------------------------------------------
# rank_players
# ---------------------------------------------------------------------------

class TestRankPlayers:
    def test_goals_p90_premier_league_fwd(self):
        from services.stats_service import rank_players
        results = rank_players(metric="goals_p90", league="Premier League", position="FWD")
        assert len(results) > 0
        # sorted descending
        values = [r.metric_value for r in results]
        assert values == sorted(values, reverse=True)

    def test_rank_field_sequential(self):
        from services.stats_service import rank_players
        results = rank_players(metric="xg_p90", league="La Liga")
        for i, r in enumerate(results):
            assert r.rank == i + 1

    def test_default_limit_is_10(self):
        from services.stats_service import rank_players
        results = rank_players(metric="goals_p90", league="Premier League")
        assert len(results) <= 10

    def test_custom_limit(self):
        from services.stats_service import rank_players
        results = rank_players(metric="assists_p90", league="Premier League", limit=5)
        assert len(results) <= 5

    def test_limit_clamped_to_max(self):
        from services.stats_service import rank_players, MAX_RANK_LIMIT
        results = rank_players(metric="goals_p90", limit=9999)
        assert len(results) <= MAX_RANK_LIMIT

    def test_max_age_filter(self):
        from services.stats_service import rank_players
        results = rank_players(metric="goals_p90", max_age=23, limit=50)
        assert all(r.metric_value >= 0 for r in results)
        # verify ages via player lookup
        from services.data_service import get_player_by_id
        for r in results:
            p = get_player_by_id(r.player_id)
            assert p is not None and p.age <= 23

    def test_min_age_filter(self):
        from services.stats_service import rank_players
        results = rank_players(metric="goals_p90", min_age=30, limit=50)
        from services.data_service import get_player_by_id
        for r in results:
            p = get_player_by_id(r.player_id)
            assert p is not None and p.age >= 30

    def test_raw_metric_alias(self):
        from services.stats_service import rank_players
        results = rank_players(metric="goals", league="Premier League", limit=5)
        assert len(results) > 0
        values = [r.metric_value for r in results]
        assert values == sorted(values, reverse=True)

    def test_unsupported_metric_raises_value_error(self):
        from services.stats_service import rank_players
        with pytest.raises(ValueError, match="Unknown metric"):
            rank_players(metric="not_a_real_metric")

    def test_returns_ranked_player_objects(self):
        from services.stats_service import rank_players
        from models.player import RankedPlayer
        results = rank_players(metric="xg_p90", league="Serie A", position="FWD")
        for r in results:
            assert isinstance(r, RankedPlayer)

    def test_metric_label_in_result(self):
        from services.stats_service import rank_players
        results = rank_players(metric="goals_p90", league="Premier League", limit=3)
        for r in results:
            assert "per 90" in r.metric_label.lower() or "goal" in r.metric_label.lower()

    def test_unsupported_metric_custom_csv(self, tmp_path, monkeypatch):
        rows = [_row(player_id="t1", minutes_played=500)]
        _patch_csv(monkeypatch, tmp_path, rows)
        from services.stats_service import rank_players
        with pytest.raises(ValueError, match="Unknown metric"):
            rank_players(metric="fantasy_points")
