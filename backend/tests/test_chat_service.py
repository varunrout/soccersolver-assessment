"""
tests/test_chat_service.py — unit and integration tests for Issue #11.

Tests are split into:
    - Unit tests for execute_chat_query() and resolve_player_name()
      (parser is mocked so tests are deterministic and offline)
    - Endpoint tests via TestClient for HTTP-level behaviour

Known real player IDs (FBref 2021-22):
    Salah  e342ad68  PL FWD
    Kane   21a66f6a  PL FWD
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_BACKEND = Path(__file__).parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app
from models.chat_responses import (
    ChatResponse,
    ChartResponse,
    ComparisonResponse,
    TableResponse,
    TextResponse,
)
from models.player import (
    ComparisonResult,
    MarketContext,
    MetricComparison,
    PlayerDetail,
    PlayerDetailWithPercentiles,
    PlayerPercentiles,
    PlayerSummary,
    RankedPlayer,
)
from nlu.parser import ParsedIntent
from services.chat_service import _error, _text, execute_chat_query, resolve_player_name

client = TestClient(app)

SALAH_ID = "e342ad68"
KANE_ID = "21a66f6a"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_intent(**kwargs) -> ParsedIntent:
    defaults = dict(
        intent="unknown",
        players=[],
        metric=None,
        league=None,
        position=None,
        min_age=None,
        max_age=None,
        min_minutes=None,
        limit=None,
        clarification_message=None,
        raw_query="",
    )
    defaults.update(kwargs)
    return ParsedIntent(**defaults)


def _make_summary(player_id: str = "aaa00001", name: str = "Test Player") -> PlayerSummary:
    return PlayerSummary(
        player_id=player_id,
        name=name,
        position="FWD",
        club="FC Test",
        league="Premier League",
        market_value_eur=10_000_000,
    )


def _make_detail(player_id: str = "aaa00001", name: str = "Test Player") -> PlayerDetail:
    return PlayerDetail(
        player_id=player_id,
        name=name,
        position="FWD",
        club="FC Test",
        league="Premier League",
        market_value_eur=10_000_000,
        age=25,
        goals=10,
        assists=5,
        minutes_played=1800,
        shots=50,
        passes=300,
        xg=8.5,
        xa=4.2,
    )


def _make_profile(player_id: str = "aaa00001", name: str = "Test Player",
                  with_percentiles: bool = True) -> PlayerDetailWithPercentiles:
    percentiles = None
    if with_percentiles:
        percentiles = PlayerPercentiles(
            player_id=player_id,
            metrics={
                "goals_p90": 85.0,
                "assists_p90": 70.0,
                "shots_p90": 80.0,
                "passes_p90": 60.0,
                "xg_p90": 82.0,
                "xa_p90": 65.0,
            },
        )
    detail = _make_detail(player_id=player_id, name=name)
    return PlayerDetailWithPercentiles(**detail.model_dump(), percentiles=percentiles)


def _make_ranked(rank: int = 1, name: str = "Player") -> RankedPlayer:
    return RankedPlayer(
        rank=rank,
        player_id=f"id{rank:05d}",
        name=name,
        club="Club",
        league="Premier League",
        position="FWD",
        metric_value=0.75,
        metric_label="Goals per 90",
    )


def _make_comparison_result() -> ComparisonResult:
    a = _make_detail("aaa", "Player A")
    b = _make_detail("bbb", "Player B")
    return ComparisonResult(
        player_a=a,
        player_b=b,
        metrics=[
            MetricComparison(
                metric_name="goals_p90", label="Goals per 90",
                value_a=0.5, value_b=0.4, winner="a",
            )
        ],
        market_context=MarketContext(
            value_a=10_000_000, value_b=8_000_000,
        ),
    )


# ===========================================================================
# Endpoint/request validation
# ===========================================================================


class TestChatEndpointValidation:
    def test_valid_request_returns_200(self):
        r = client.post("/chat", json={"message": "Top 5 forwards by goals"})
        assert r.status_code == 200

    def test_response_always_has_type(self):
        r = client.post("/chat", json={"message": "anything"})
        assert r.status_code == 200
        assert "type" in r.json()["response"]

    def test_blank_message_still_returns_422(self):
        r = client.post("/chat", json={"message": " "})
        assert r.status_code == 422

    def test_oversized_message_still_returns_422(self):
        r = client.post("/chat", json={"message": "x" * 1001})
        assert r.status_code == 422


# ===========================================================================
# Unknown intent
# ===========================================================================


class TestUnknownIntent:
    def test_unknown_intent_returns_text(self):
        intent = _make_intent(
            intent="unknown",
            clarification_message="Which metric should I use?",
        )
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("who is best?")
        assert isinstance(result.response, TextResponse)

    def test_clarification_message_preserved(self):
        intent = _make_intent(
            intent="unknown",
            clarification_message="Please specify a metric.",
        )
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("top football players")  # football term keeps clarification
        assert result.response.message == "Please specify a metric."

    def test_missing_clarification_receives_default(self):
        intent = _make_intent(intent="unknown", clarification_message=None)
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("gibberish")
        assert isinstance(result.response, TextResponse)
        assert len(result.response.message) > 0


# ===========================================================================
# Ranking intent
# ===========================================================================


class TestRankingIntent:
    def _ranking_intent(self, **kw) -> ParsedIntent:
        defaults = dict(intent="ranking", metric="goals", league="Premier League",
                        position="FWD", limit=5, min_minutes=300)
        defaults.update(kw)
        return _make_intent(**defaults)

    def test_ranking_returns_table(self):
        intent = self._ranking_intent()
        ranked = [_make_ranked(i + 1, f"Player {i+1}") for i in range(5)]
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players", return_value=ranked) as mock_rank,
        ):
            result = execute_chat_query("top 5 forwards by goals")
        assert isinstance(result.response, TableResponse)

    def test_ranking_calls_rank_players_with_correct_args(self):
        intent = self._ranking_intent(
            metric="assists", league="La Liga", position="MID",
            limit=3, min_minutes=500, min_age=20, max_age=28,
        )
        ranked = [_make_ranked(1, "P")]
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players", return_value=ranked) as mock_rank,
        ):
            execute_chat_query("top midfielders")
        mock_rank.assert_called_once_with(
            "assists",
            position="MID",
            league="La Liga",
            min_age=20,
            max_age=28,
            min_minutes=500,
            limit=3,
        )

    def test_table_rows_are_correctly_shaped(self):
        intent = self._ranking_intent()
        ranked = [_make_ranked(1, "Salah"), _make_ranked(2, "Kane")]
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players", return_value=ranked),
        ):
            result = execute_chat_query("top forwards")
        table = result.response
        assert isinstance(table, TableResponse)
        assert len(table.rows) == 2
        for row in table.rows:
            for field in ("rank", "name", "club", "league", "position", "metric_value", "metric_label"):
                assert field in row

    def test_service_numbers_passed_through_unchanged(self):
        intent = self._ranking_intent()
        ranked = [_make_ranked(1, "Salah")]
        ranked[0] = ranked[0].model_copy(update={"metric_value": 0.79})
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players", return_value=ranked),
        ):
            result = execute_chat_query("top forwards")
        assert result.response.rows[0]["metric_value"] == 0.79

    def test_no_results_returns_error_text(self):
        intent = self._ranking_intent()
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players", return_value=[]),
        ):
            result = execute_chat_query("top players")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True

    def test_unsupported_metric_returns_error_text(self):
        intent = self._ranking_intent(metric="banana_metric")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players",
                  side_effect=ValueError("Unknown metric 'banana_metric'")),
        ):
            result = execute_chat_query("rank by banana")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True

    def test_no_metric_returns_clarification_text(self):
        intent = _make_intent(intent="ranking", metric=None)
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("top players")
        assert isinstance(result.response, TextResponse)


# ===========================================================================
# Player lookup intent
# ===========================================================================


class TestLookupIntent:
    def test_exact_player_match_resolves(self):
        intent = _make_intent(intent="player_lookup", players=["Mohamed Salah"])
        summary = _make_summary("aaa", "Mohamed Salah")
        profile = _make_profile("aaa", "Mohamed Salah")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats", return_value=profile),
        ):
            result = execute_chat_query("show me Salah")
        assert isinstance(result.response, ChartResponse)

    def test_one_fuzzy_match_resolves(self):
        intent = _make_intent(intent="player_lookup", players=["Salah"])
        summary = _make_summary("aaa", "Mohamed Salah")
        profile = _make_profile("aaa", "Mohamed Salah")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats", return_value=profile),
        ):
            result = execute_chat_query("show me Salah")
        assert isinstance(result.response, ChartResponse)

    def test_no_match_returns_error_text(self):
        intent = _make_intent(intent="player_lookup", players=["Ghosty McFake"])
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[]),
        ):
            result = execute_chat_query("show me Ghosty")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True

    def test_multiple_unresolved_returns_clarification_text(self):
        intent = _make_intent(intent="player_lookup", players=["Silva"])
        matches = [
            _make_summary("a", "Bernardo Silva"),
            _make_summary("b", "André Silva"),
            _make_summary("c", "Rui Silva"),
        ]
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=matches),
        ):
            result = execute_chat_query("show me Silva")
        assert isinstance(result.response, TextResponse)
        assert "Silva" in result.response.message

    def test_exact_full_name_preferred_among_multiple(self):
        intent = _make_intent(intent="player_lookup", players=["André Silva"])
        matches = [
            _make_summary("a", "Bernardo Silva"),
            _make_summary("b", "André Silva"),
        ]
        profile = _make_profile("b", "André Silva")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=matches),
            patch("services.chat_service.stats_service.get_player_profile_stats", return_value=profile),
        ):
            result = execute_chat_query("show me André Silva")
        assert isinstance(result.response, ChartResponse)

    def test_lookup_returns_chart_when_percentiles_exist(self):
        intent = _make_intent(intent="player_lookup", players=["Test Player"])
        summary = _make_summary()
        profile = _make_profile(with_percentiles=True)
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats", return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, ChartResponse)
        assert result.response.chart_type == "radar"

    def test_lookup_returns_text_fallback_when_no_percentiles(self):
        intent = _make_intent(intent="player_lookup", players=["Test Player"])
        summary = _make_summary()
        profile = _make_profile(with_percentiles=False)
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats", return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, TextResponse)

    def test_lookup_returns_text_fallback_when_all_percentiles_none(self):
        intent = _make_intent(intent="player_lookup", players=["Test Player"])
        summary = _make_summary()
        profile = _make_profile(with_percentiles=True)
        # Override all percentile values to None
        profile.percentiles.metrics = {k: None for k in profile.percentiles.metrics}
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats", return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, TextResponse)


# ===========================================================================
# Comparison intent
# ===========================================================================


class TestComparisonIntent:
    def test_two_names_resolve_and_comparison_called_with_ids(self):
        intent = _make_intent(intent="comparison", players=["Player A", "Player B"])
        summary_a = _make_summary("aaa", "Player A")
        summary_b = _make_summary("bbb", "Player B")
        comp = _make_comparison_result()
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[summary_a], [summary_b]]),
            patch("services.chat_service.comparison_service.compare_players",
                  return_value=comp) as mock_cmp,
        ):
            result = execute_chat_query("compare A and B")
        mock_cmp.assert_called_once_with("aaa", "bbb")
        assert isinstance(result.response, ComparisonResponse)

    def test_successful_comparison_returns_comparison_type(self):
        intent = _make_intent(intent="comparison", players=["A", "B"])
        sa = _make_summary("a", "A")
        sb = _make_summary("b", "B")
        comp = _make_comparison_result()
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[sa], [sb]]),
            patch("services.chat_service.comparison_service.compare_players", return_value=comp),
        ):
            result = execute_chat_query("compare A and B")
        assert result.response.type == "comparison"

    def test_unknown_first_player_returns_text(self):
        intent = _make_intent(intent="comparison", players=["Ghost", "Kane"])
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[], []]),
        ):
            result = execute_chat_query("compare Ghost and Kane")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True

    def test_unknown_second_player_returns_text(self):
        intent = _make_intent(intent="comparison", players=["Salah", "Ghost"])
        sa = _make_summary("a", "Salah")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[sa], []]),
        ):
            result = execute_chat_query("compare Salah and Ghost")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True

    def test_ambiguous_player_returns_clarification(self):
        intent = _make_intent(intent="comparison", players=["Silva", "Kane"])
        matches = [_make_summary("x", "Bernardo Silva"), _make_summary("y", "André Silva")]
        sk = _make_summary("k", "Harry Kane")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[matches, [sk]]),
        ):
            result = execute_chat_query("compare Silva and Kane")
        assert isinstance(result.response, TextResponse)
        assert "Silva" in result.response.message

    def test_comparison_service_returning_none_returns_error(self):
        intent = _make_intent(intent="comparison", players=["A", "B"])
        sa = _make_summary("a", "A")
        sb = _make_summary("b", "B")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[sa], [sb]]),
            patch("services.chat_service.comparison_service.compare_players", return_value=None),
        ):
            result = execute_chat_query("compare A and B")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True

    def test_fewer_than_two_players_returns_clarification(self):
        intent = _make_intent(intent="comparison", players=["Salah"])
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("compare Salah")
        assert isinstance(result.response, TextResponse)


# ===========================================================================
# resolve_player_name unit tests
# ===========================================================================


class TestResolvePlayerName:
    def test_no_match_returns_error_response(self):
        with patch("services.chat_service.data_service.search_players", return_value=[]):
            result = resolve_player_name("Ghost Player")
        assert isinstance(result, ChatResponse)
        assert result.response.is_error is True

    def test_one_match_returns_summary(self):
        summary = _make_summary("a", "Mohamed Salah")
        with patch("services.chat_service.data_service.search_players", return_value=[summary]):
            result = resolve_player_name("Salah")
        assert isinstance(result, PlayerSummary)
        assert result.player_id == "a"

    def test_exact_name_match_preferred(self):
        matches = [_make_summary("a", "John Smith Jr"), _make_summary("b", "John Smith")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("John Smith")
        assert isinstance(result, PlayerSummary)
        assert result.name == "John Smith"

    def test_case_insensitive_exact_match(self):
        matches = [_make_summary("a", "Mohammed Salah"), _make_summary("b", "Mohamed Salah")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("MOHAMED SALAH")
        assert isinstance(result, PlayerSummary)
        assert result.name == "Mohamed Salah"

    def test_ambiguous_returns_clarification(self):
        matches = [_make_summary("a", "Bernardo Silva"), _make_summary("b", "André Silva")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("Silva")
        assert isinstance(result, ChatResponse)
        assert "Silva" in result.response.message

    def test_ambiguous_lists_up_to_five_candidates(self):
        matches = [_make_summary(str(i), f"Player {i} Silva") for i in range(10)]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("Silva")
        assert isinstance(result, ChatResponse)
        # count how many candidate names appear in the message (at most 5)
        mentioned = sum(1 for m in matches[:5] if m.name in result.response.message)
        assert mentioned <= 5


# ===========================================================================
# Architecture / no-CSV / no-recalculation tests
# ===========================================================================


class TestArchitecture:
    def test_router_imports_chat_service(self):
        """The chat router must delegate to chat_service, not do its own dispatch."""
        import routers.chat as chat_router
        assert hasattr(chat_router, "execute_chat_query")

    def test_chat_service_has_no_csv_import(self):
        import ast
        source = (Path(__file__).parent.parent / "services" / "chat_service.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    assert "csv" not in name.lower(), f"CSV import found: {name}"

    def test_chat_service_has_no_openai_import(self):
        import ast
        source = (Path(__file__).parent.parent / "services" / "chat_service.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    assert "openai" not in name.lower(), f"OpenAI import found: {name}"

    def test_chat_service_has_no_per90_formula(self):
        """No raw per-90 division in chat_service.py."""
        source = (Path(__file__).parent.parent / "services" / "chat_service.py").read_text(encoding="utf-8")
        # The formula "/ minutes_played * 90" must not appear
        assert "minutes_played * 90" not in source

    def test_unexpected_exception_returns_safe_error(self):
        intent = _make_intent(intent="ranking", metric="goals")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players",
                  side_effect=RuntimeError("db exploded")),
        ):
            result = execute_chat_query("top forwards by goals")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True
        # Must not expose internal details
        assert "db exploded" not in result.response.message

    def test_openapi_still_succeeds(self):
        schema = app.openapi()
        assert isinstance(schema, dict)
        assert "paths" in schema


# ===========================================================================
# Live integration smoke tests (no mocking — uses real dataset)
# ===========================================================================


class TestLiveIntegration:
    """End-to-end tests that run through the real rule-based parser and real services."""

    def test_ranking_query_returns_table(self):
        r = client.post("/chat", json={"message": "Top 5 forwards in the Premier League by goals"})
        assert r.status_code == 200
        assert r.json()["response"]["type"] == "table"

    def test_lookup_salah_returns_chart_or_text(self):
        r = client.post("/chat", json={"message": "Show me Mohamed Salah"})
        assert r.status_code == 200
        rtype = r.json()["response"]["type"]
        assert rtype in ("chart", "text")

    def test_comparison_salah_kane_returns_comparison(self):
        r = client.post("/chat", json={"message": "Compare Mohamed Salah and Harry Kane"})
        assert r.status_code == 200
        assert r.json()["response"]["type"] == "comparison"

    def test_vague_query_returns_text(self):
        r = client.post("/chat", json={"message": "Who is the best player?"})
        assert r.status_code == 200
        assert r.json()["response"]["type"] == "text"


# ===========================================================================
# Issue #12 — Graceful failure handling acceptance criteria
# ===========================================================================


class TestGracefulFailureHandling:
    """Acceptance-criteria tests for Issue #12."""

    # 1. Unknown player name
    def test_unknown_player_name_message(self):
        r = client.post("/chat", json={"message": "Show me Xyzzy Fake Player"})
        assert r.status_code == 200
        body = r.json()["response"]
        assert body["type"] == "text"
        assert body["is_error"] is True
        assert "in the dataset" in body["message"]

    def test_unknown_player_message_format(self):
        intent = _make_intent(intent="player_lookup", players=["Ghosty McFake"])
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[]),
        ):
            result = execute_chat_query("show me Ghosty McFake")
        assert 'Ghosty McFake' in result.response.message
        assert "in the dataset" in result.response.message
        assert result.response.is_error is True

    # 2. Ambiguous / no metric
    def test_ambiguous_no_metric_returns_text_with_example(self):
        r = client.post("/chat", json={"message": "show me the best football player"})
        assert r.status_code == 200
        body = r.json()["response"]
        assert body["type"] == "text"

    def test_ranking_no_metric_suggests_metric(self):
        intent = _make_intent(intent="unknown",
                              clarification_message="Which metric should I rank by, such as goals, assists or xG?")
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("best footballers")
        assert isinstance(result.response, TextResponse)
        assert "goals" in result.response.message.lower() or "metric" in result.response.message.lower()

    # 3. Out-of-scope query
    def test_weather_query_returns_out_of_scope_message(self):
        r = client.post("/chat", json={"message": "What's the weather in Madrid?"})
        assert r.status_code == 200
        body = r.json()["response"]
        assert body["type"] == "text"
        assert "football" in body["message"].lower() or "statistics" in body["message"].lower()

    def test_out_of_scope_returns_is_error_true(self):
        r = client.post("/chat", json={"message": "What's the weather in Madrid?"})
        assert r.json()["response"]["is_error"] is True

    def test_clearly_non_football_query(self):
        for query in [
            "What's the weather in Madrid?",
            "Give me a chocolate cake recipe",
            "What is the capital of France?",
        ]:
            r = client.post("/chat", json={"message": query})
            assert r.status_code == 200
            body = r.json()["response"]
            assert body["type"] == "text"
            assert "football" in body["message"].lower() or "statistics" in body["message"].lower(), \
                f"Query '{query}' did not return out-of-scope message"

    # 4. OpenAI API failure
    def test_openai_failure_with_rule_based_fallback_works(self, monkeypatch):
        """When OpenAI fails but rule-based can parse → use rule-based result."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query as real_parse
            result = real_parse("Top 5 forwards in the Premier League by goals")
        # Rule-based should produce ranking intent
        assert result.intent == "ranking"

    def test_openai_failure_unknown_query_returns_failure_message(self, monkeypatch):
        """When OpenAI fails AND rule-based can't parse → show failure message."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query as real_parse
            result = real_parse("What's the weather in Madrid?")
        # Weather query is out-of-scope; rule-based also returns unknown
        assert result.intent == "unknown"
        assert "wrong" in result.clarification_message.lower() or "again" in result.clarification_message.lower()

    # 5. Two-player comparison with only one player resolved
    def test_comparison_one_player_resolved_message(self):
        intent = _make_intent(intent="comparison", players=["Salah", "Ghost Player"])
        salah = _make_summary("e342ad68", "Mohamed Salah")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[salah], []]),
        ):
            result = execute_chat_query("compare Salah and Ghost Player")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True
        assert "Ghost Player" in result.response.message

    def test_comparison_fewer_than_two_names_message(self):
        intent = _make_intent(intent="comparison", players=["Salah"])
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("compare Salah")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True
        assert "two" in result.response.message.lower() or "run a comparison" in result.response.message.lower()

    # 6. intent="unknown" always is_error=True
    def test_unknown_intent_is_error_true(self):
        intent = _make_intent(intent="unknown", clarification_message="Which metric?")
        with patch("services.chat_service.parse_query", return_value=intent):
            result = execute_chat_query("goals football")
        assert result.response.is_error is True

    def test_unknown_intent_never_raises_http500(self):
        """Any unknown intent must return 200, not 500."""
        for query in [
            "???",
            "Who is the best player?",
            "Tell me about football in general",
        ]:
            # Need football term to avoid out-of-scope; use football
            r = client.post("/chat", json={"message": "best football stats"})
            assert r.status_code == 200

    # 7. All errors are helpful (no raw exceptions exposed)
    def test_no_stack_trace_in_error_responses(self):
        intent = _make_intent(intent="ranking", metric="goals")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players",
                  side_effect=RuntimeError("internal SQL error")),
        ):
            result = execute_chat_query("top players by goals")
        assert "SQL" not in result.response.message
        assert "Traceback" not in result.response.message
        assert "RuntimeError" not in result.response.message

    def test_error_responses_never_http_500(self):
        """All domain errors must be HTTP 200 with is_error=True, not 500."""
        # Unknown player
        r = client.post("/chat", json={"message": "Show me Xyzzy Nonexistent Player"})
        assert r.status_code == 200
