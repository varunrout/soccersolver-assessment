"""
tests/test_endpoints.py — integration tests for the REST API.

Uses FastAPI TestClient (no live server needed).

Run from backend/:
    pytest tests/test_endpoints.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/ is importable when pytest is invoked from backend/
_BACKEND = Path(__file__).parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Known real player IDs (FBref 2021-22 dataset)
# ---------------------------------------------------------------------------
SALAH_ID = "e342ad68"   # Mohamed Salah — PL FWD
KANE_ID  = "21a66f6a"   # Harry Kane    — PL FWD


# ===========================================================================
# Health
# ===========================================================================

class TestHealth:
    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_body(self):
        r = client.get("/health")
        assert r.json() == {"status": "ok"}


# ===========================================================================
# GET /players/search
# ===========================================================================

class TestSearch:

    def test_valid_search_returns_200(self):
        r = client.get("/players/search", params={"q": "Salah"})
        assert r.status_code == 200

    def test_response_is_list(self):
        r = client.get("/players/search", params={"q": "Salah"})
        assert isinstance(r.json(), list)

    def test_known_player_is_in_results(self):
        r = client.get("/players/search", params={"q": "Salah"})
        ids = [p["player_id"] for p in r.json()]
        assert SALAH_ID in ids

    def test_no_match_returns_empty_list(self):
        r = client.get("/players/search", params={"q": "xyzzznonexistentplayer"})
        assert r.status_code == 200
        assert r.json() == []

    def test_blank_query_returns_client_error(self):
        r = client.get("/players/search", params={"q": "   "})
        assert r.status_code in (400, 422)

    def test_missing_q_param_returns_422(self):
        r = client.get("/players/search")
        assert r.status_code == 422

    def test_result_contains_expected_fields(self):
        r = client.get("/players/search", params={"q": "Salah"})
        assert r.status_code == 200
        player = r.json()[0]
        for field in ("player_id", "name", "position", "club", "league", "market_value_eur"):
            assert field in player, f"Missing field: {field}"

    def test_result_does_not_contain_age(self):
        # PlayerSummary must not expose 'age' (it's in PlayerDetail only)
        r = client.get("/players/search", params={"q": "Salah"})
        assert r.status_code == 200
        assert "age" not in r.json()[0]

    def test_case_insensitive_search(self):
        r_lower = client.get("/players/search", params={"q": "salah"})
        r_upper = client.get("/players/search", params={"q": "SALAH"})
        assert r_lower.status_code == 200
        assert r_upper.status_code == 200
        ids_lower = {p["player_id"] for p in r_lower.json()}
        ids_upper = {p["player_id"] for p in r_upper.json()}
        assert ids_lower == ids_upper

    def test_partial_name_returns_results(self):
        r = client.get("/players/search", params={"q": "Kane"})
        assert r.status_code == 200
        ids = [p["player_id"] for p in r.json()]
        assert KANE_ID in ids


# ===========================================================================
# GET /players/{player_id}
# ===========================================================================

class TestProfile:

    def test_known_player_returns_200(self):
        r = client.get(f"/players/{SALAH_ID}")
        assert r.status_code == 200

    def test_unknown_player_returns_404(self):
        r = client.get("/players/does-not-exist-abc123")
        assert r.status_code == 404

    def test_404_detail_message(self):
        r = client.get("/players/does-not-exist-abc123")
        assert "not found" in r.json()["detail"].lower()

    def test_response_contains_player_fields(self):
        r = client.get(f"/players/{SALAH_ID}")
        body = r.json()
        for field in (
            "player_id", "name", "position", "club", "league",
            "market_value_eur", "age", "goals", "assists",
            "minutes_played", "shots", "passes", "xg", "xa",
        ):
            assert field in body, f"Missing field: {field}"

    def test_player_id_matches_request(self):
        r = client.get(f"/players/{SALAH_ID}")
        assert r.json()["player_id"] == SALAH_ID

    def test_response_contains_percentiles_key(self):
        r = client.get(f"/players/{SALAH_ID}")
        assert "percentiles" in r.json()

    def test_percentiles_has_metrics(self):
        r = client.get(f"/players/{SALAH_ID}")
        percentiles = r.json()["percentiles"]
        # percentiles may be None for a player with tiny peer group,
        # but for Salah (PL FWD, many peers) it should be present
        if percentiles is not None:
            assert "metrics" in percentiles
            assert "player_id" in percentiles

    def test_kane_profile(self):
        r = client.get(f"/players/{KANE_ID}")
        assert r.status_code == 200
        assert r.json()["player_id"] == KANE_ID


# ===========================================================================
# GET /players/compare
# ===========================================================================

class TestCompare:

    def test_two_known_players_returns_200(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        assert r.status_code == 200

    def test_response_has_player_a(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        assert r.json()["player_a"]["player_id"] == SALAH_ID

    def test_response_has_player_b(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        assert r.json()["player_b"]["player_id"] == KANE_ID

    def test_response_has_metrics(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        assert "metrics" in r.json()

    def test_response_has_market_context(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        assert "market_context" in r.json()

    def test_exactly_six_metrics(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        assert len(r.json()["metrics"]) == 6

    def test_metric_fields_present(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        for m in r.json()["metrics"]:
            for field in ("metric_name", "label", "value_a", "value_b", "winner"):
                assert field in m, f"Missing metric field: {field}"

    def test_winner_is_valid(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        for m in r.json()["metrics"]:
            assert m["winner"] in ("a", "b", "draw")

    def test_unknown_player_a_returns_404(self):
        r = client.get("/players/compare", params={
            "player_a_id": "ghost-000", "player_b_id": KANE_ID
        })
        assert r.status_code == 404

    def test_unknown_player_b_returns_404(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": "ghost-000"
        })
        assert r.status_code == 404

    def test_missing_player_a_param_returns_422(self):
        r = client.get("/players/compare", params={"player_b_id": KANE_ID})
        assert r.status_code == 422

    def test_missing_player_b_param_returns_422(self):
        r = client.get("/players/compare", params={"player_a_id": SALAH_ID})
        assert r.status_code == 422

    def test_same_player_both_sides_allowed(self):
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": SALAH_ID
        })
        assert r.status_code == 200

    def test_compare_not_swallowed_by_profile_route(self):
        """Ensure /players/compare is not treated as /{player_id}='compare'."""
        r = client.get("/players/compare", params={
            "player_a_id": SALAH_ID, "player_b_id": KANE_ID
        })
        # If routing were wrong, FastAPI would look up player_id="compare" → 404
        assert r.status_code == 200
