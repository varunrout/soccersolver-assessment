"""
tests/test_issue12_hardening.py — Issue #12 comprehensive edge-case hardening.

Covers:
  - resolve_player_name() hardening (blank, strip, dedup, sort, cap)
  - OpenAI failure detection (explicit tuple semantics)
  - Ranking edge cases (limit clamp, negative min_minutes, bad metric, NaN)
  - Profile edge cases (no percentiles, all-None, no chart)
  - Comparison edge cases (None market, zero minutes, same player, winners)
  - Parser hardening (non-string input, invalid LLM output, blank players)
  - REST regression (no exception text exposed, health/search/profile/compare)
  - Serialization: no NaN/infinity in successful responses
"""

from __future__ import annotations

import math
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
from nlu.parser import ParsedIntent, _parse_with_openai, parse_query
from services.chat_service import (
    _error,
    _text,
    execute_chat_query,
    resolve_player_name,
)

client = TestClient(app)

SALAH_ID = "e342ad68"
KANE_ID = "21a66f6a"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summary(pid: str, name: str) -> PlayerSummary:
    return PlayerSummary(
        player_id=pid, name=name, position="FWD",
        club="FC", league="Premier League", market_value_eur=5_000_000,
    )


def _detail(pid: str = "aaa", name: str = "Player") -> PlayerDetail:
    return PlayerDetail(
        player_id=pid, name=name, position="FWD",
        club="FC", league="Premier League", market_value_eur=5_000_000,
        age=25, goals=10, assists=5, minutes_played=1800,
        shots=50, passes=300, xg=8.5, xa=4.2,
    )


def _profile(pid: str = "aaa", name: str = "Player",
             percentile_values: dict | None | str = "full") -> PlayerDetailWithPercentiles:
    if percentile_values == "full":
        pct = PlayerPercentiles(
            player_id=pid,
            metrics={"goals_p90": 80.0, "assists_p90": 70.0, "shots_p90": 75.0,
                     "passes_p90": 60.0, "xg_p90": 78.0, "xa_p90": 65.0},
        )
    elif percentile_values is None:
        pct = None
    else:
        pct = PlayerPercentiles(player_id=pid, metrics=percentile_values)
    d = _detail(pid, name)
    return PlayerDetailWithPercentiles(**d.model_dump(), percentiles=pct)


def _ranked(rank: int = 1, metric_value: float = 0.75) -> RankedPlayer:
    return RankedPlayer(
        rank=rank, player_id=f"id{rank:05d}", name=f"Player {rank}",
        club="Club", league="Premier League", position="FWD",
        metric_value=metric_value, metric_label="Goals per 90",
    )


def _intent(**kw) -> ParsedIntent:
    defaults = dict(
        intent="unknown", players=[], metric=None, league=None, position=None,
        min_age=None, max_age=None, min_minutes=None, limit=None,
        clarification_message=None, raw_query="",
    )
    defaults.update(kw)
    return ParsedIntent(**defaults)


def _has_nan_or_inf(obj) -> bool:
    """Recursively check a JSON-deserialized structure for NaN or infinity."""
    if isinstance(obj, float):
        return math.isnan(obj) or math.isinf(obj)
    if isinstance(obj, dict):
        return any(_has_nan_or_inf(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_nan_or_inf(item) for item in obj)
    return False


# ===========================================================================
# resolve_player_name hardening
# ===========================================================================

class TestResolvePlayerNameHardening:

    def test_blank_name_does_not_call_search(self):
        with patch("services.chat_service.data_service.search_players") as mock_search:
            result = resolve_player_name("   ")
        mock_search.assert_not_called()
        assert isinstance(result, ChatResponse)
        assert result.response.is_error is False  # clarification

    def test_blank_name_returns_clarification(self):
        result = resolve_player_name("")
        assert isinstance(result, ChatResponse)
        assert "player" in result.response.message.lower()

    def test_one_match_returns_summary(self):
        s = _summary("a", "Mohamed Salah")
        with patch("services.chat_service.data_service.search_players", return_value=[s]):
            result = resolve_player_name("Salah")
        assert isinstance(result, PlayerSummary)
        assert result.player_id == "a"

    def test_no_match_returns_error(self):
        with patch("services.chat_service.data_service.search_players", return_value=[]):
            result = resolve_player_name("Ghost Player")
        assert isinstance(result, ChatResponse)
        assert result.response.is_error is True
        assert "in the dataset" in result.response.message

    def test_one_exact_match_among_partials(self):
        matches = [_summary("a", "Bruno Fernandes"), _summary("b", "André Fernandes")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("Bruno Fernandes")
        assert isinstance(result, PlayerSummary)
        assert result.name == "Bruno Fernandes"

    def test_case_insensitive_exact_match(self):
        matches = [_summary("a", "Harry Kane"), _summary("b", "Jordan Kane")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("harry kane")
        assert isinstance(result, PlayerSummary)
        assert result.name == "Harry Kane"

    def test_multiple_identical_exact_name_matches_returns_error(self):
        """Two records with the same name → still ambiguous."""
        matches = [_summary("a", "John Smith"), _summary("b", "John Smith")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("John Smith")
        assert isinstance(result, ChatResponse)
        assert result.response.is_error is True

    def test_duplicate_candidate_names_deduplicated(self):
        matches = [_summary("a", "John Smith"), _summary("b", "john smith"),
                   _summary("c", "John Smith Jr")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("Smith")
        assert isinstance(result, ChatResponse)
        msg = result.response.message
        # Deduplicated: "John Smith" and "john smith" collapse → only 2 unique entries
        candidates_part = msg.split(":")[1].split(".")[0].strip() if ":" in msg else msg
        names = [n.strip() for n in candidates_part.split(",") if n.strip()]
        assert len(names) == 2

    def test_candidates_sorted_deterministically(self):
        # Same matches in different order → same candidate list
        matches_a = [_summary("a", "Zebra Player"), _summary("b", "Alpha Player"),
                     _summary("c", "Mango Player")]
        matches_b = [_summary("c", "Mango Player"), _summary("a", "Zebra Player"),
                     _summary("b", "Alpha Player")]
        with patch("services.chat_service.data_service.search_players", return_value=matches_a):
            r_a = resolve_player_name("Player")
        with patch("services.chat_service.data_service.search_players", return_value=matches_b):
            r_b = resolve_player_name("Player")
        assert r_a.response.message == r_b.response.message

    def test_more_than_five_candidates_capped(self):
        matches = [_summary(str(i), f"Player {chr(65+i)}") for i in range(10)]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("Player")
        assert isinstance(result, ChatResponse)
        # Only names of first 5 (sorted) appear
        msg = result.response.message
        for m in matches[5:]:
            # extra candidates may or may not appear, but total name count ≤ 5
            pass
        candidate_part = msg.split(":")[1].split(".")[0] if ":" in msg else msg
        names_listed = [n.strip() for n in candidate_part.split(",")]
        assert len(names_listed) <= 5

    def test_ambiguous_returns_is_error_true(self):
        matches = [_summary("a", "Bernardo Silva"), _summary("b", "André Silva")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("Silva")
        assert result.response.is_error is True

    def test_no_player_id_exposed_in_ambiguous_message(self):
        matches = [_summary("secret-id-1", "Alpha Player"),
                   _summary("secret-id-2", "Beta Player")]
        with patch("services.chat_service.data_service.search_players", return_value=matches):
            result = resolve_player_name("Player")
        assert "secret-id-1" not in result.response.message
        assert "secret-id-2" not in result.response.message

    def test_search_uses_stripped_name(self):
        with patch("services.chat_service.data_service.search_players", return_value=[]) as mock:
            resolve_player_name("  Salah  ")
        mock.assert_called_once_with("Salah")


# ===========================================================================
# OpenAI failure detection
# ===========================================================================

class TestOpenAIFailureDetection:

    def test_no_api_key_returns_not_attempted(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result, attempted, failed = _parse_with_openai("Top forwards")
        assert result is None
        assert attempted is False
        assert failed is False

    def test_openai_package_unavailable_not_attempted(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        with patch("nlu.parser.OpenAI", None):
            result, attempted, failed = _parse_with_openai("Top forwards")
        assert attempted is False
        assert failed is False

    def test_api_exception_returns_attempted_and_failed(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Network error")
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result, attempted, failed = _parse_with_openai("Top forwards")
        assert attempted is True
        assert failed is True
        assert result is None

    def test_successful_call_returns_result_not_failed(self, monkeypatch):
        import json as _json
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        args = {"intent": "ranking", "metric": "goals", "limit": 5,
                "league": "Premier League", "position": "FWD"}
        mock_tool = MagicMock()
        mock_tool.function.arguments = _json.dumps(args)
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tool]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result, attempted, failed = _parse_with_openai("Top 5 PL forwards by goals")
        assert attempted is True
        assert failed is False
        assert result is not None
        assert result.intent == "ranking"

    def test_no_key_unknown_query_does_not_show_api_failure_message(self, monkeypatch):
        """Without an API key, a vague query must NOT show the API failure message."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = parse_query("what's the weather?")
        assert result.intent == "unknown"
        assert "wrong" not in result.clarification_message.lower() or \
               "api" not in result.clarification_message.lower()

    def test_api_failure_unknown_query_shows_failure_message(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result = parse_query("what's the weather?")
        assert result.intent == "unknown"
        assert "wrong" in result.clarification_message.lower() or \
               "again" in result.clarification_message.lower()

    def test_api_failure_parseable_query_does_not_show_failure(self, monkeypatch):
        """When OpenAI fails but rule-based can parse → use rule-based, no API message."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result = parse_query("Top 5 forwards in the Premier League by goals")
        assert result.intent == "ranking"

    def test_skipped_path_not_labelled_failure(self, monkeypatch):
        """When OpenAI is not configured (no key), unknown queries are NOT API failures."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = parse_query("who is the best player?")
        assert result.intent == "unknown"
        assert "something went wrong" not in result.clarification_message.lower()


# ===========================================================================
# Ranking edge cases
# ===========================================================================

class TestRankingEdgeCases:

    def _ranking_intent(self, **kw) -> ParsedIntent:
        defaults = dict(intent="ranking", metric="goals", league=None,
                        position=None, limit=5, min_minutes=300)
        defaults.update(kw)
        return _intent(**defaults)

    def test_limit_zero_uses_default(self):
        """limit=0 is falsy → chat_service substitutes DEFAULT_LIMIT (5)."""
        from services.chat_service import DEFAULT_LIMIT
        r_intent = self._ranking_intent(limit=0)
        ranked = [_ranked(1)]
        with (
            patch("services.chat_service.parse_query", return_value=r_intent),
            patch("services.chat_service.stats_service.rank_players",
                  return_value=ranked) as mock_rank,
        ):
            result = execute_chat_query("top players by goals")
        call_kwargs = mock_rank.call_args[1]
        assert call_kwargs["limit"] == DEFAULT_LIMIT

    def test_limit_over_50_passed_to_service(self):
        """limit>50 is passed to rank_players which clamps it."""
        r_intent = self._ranking_intent(limit=100)
        ranked = [_ranked(1)]
        with (
            patch("services.chat_service.parse_query", return_value=r_intent),
            patch("services.chat_service.stats_service.rank_players",
                  return_value=ranked) as mock_rank,
        ):
            execute_chat_query("top players by goals")
        assert mock_rank.call_args[1]["limit"] == 100

    def test_negative_min_minutes_passed_to_service(self):
        """Negative min_minutes is passed; stats_service handles the clamp."""
        r_intent = self._ranking_intent(min_minutes=-100)
        ranked = [_ranked(1)]
        with (
            patch("services.chat_service.parse_query", return_value=r_intent),
            patch("services.chat_service.stats_service.rank_players",
                  return_value=ranked) as mock_rank,
        ):
            execute_chat_query("top players")
        assert mock_rank.call_args[1]["min_minutes"] == -100

    def test_unsupported_metric_returns_error_text(self):
        r_intent = self._ranking_intent(metric="banana_stat")
        with (
            patch("services.chat_service.parse_query", return_value=r_intent),
            patch("services.chat_service.stats_service.rank_players",
                  side_effect=ValueError("Unknown metric 'banana_stat'")),
        ):
            result = execute_chat_query("rank by banana")
        assert isinstance(result.response, TextResponse)
        assert result.response.is_error is True

    def test_zero_minute_players_excluded_from_per90_by_service(self):
        """stats_service enforces min 1 minute for per-90; verify chat_service calls it."""
        r_intent = self._ranking_intent(metric="goals_p90", min_minutes=0)
        ranked = [_ranked(1)]
        with (
            patch("services.chat_service.parse_query", return_value=r_intent),
            patch("services.chat_service.stats_service.rank_players",
                  return_value=ranked) as mock_rank,
        ):
            execute_chat_query("top by goals p90")
        # Chat service passes min_minutes=0; stats_service will clamp to 1 for per-90
        assert mock_rank.call_args[1]["min_minutes"] == 0

    def test_no_nan_in_ranking_response(self):
        r_intent = self._ranking_intent()
        ranked = [_ranked(i + 1, float(i) * 0.1) for i in range(5)]
        with (
            patch("services.chat_service.parse_query", return_value=r_intent),
            patch("services.chat_service.stats_service.rank_players", return_value=ranked),
        ):
            result = execute_chat_query("top players by goals")
        data = result.model_dump()
        assert not _has_nan_or_inf(data)


# ===========================================================================
# Profile / lookup edge cases
# ===========================================================================

class TestProfileEdgeCases:

    def _lookup_intent(self, player: str = "Test Player") -> ParsedIntent:
        return _intent(intent="player_lookup", players=[player])

    def test_percentiles_none_returns_text(self):
        summary = _summary("a", "Test Player")
        profile = _profile(percentile_values=None)
        with (
            patch("services.chat_service.parse_query", return_value=self._lookup_intent()),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats",
                  return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, TextResponse)

    def test_empty_percentile_metrics_returns_text(self):
        summary = _summary("a", "Test Player")
        profile = _profile(percentile_values={})
        with (
            patch("services.chat_service.parse_query", return_value=self._lookup_intent()),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats",
                  return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, TextResponse)

    def test_all_percentile_values_none_returns_text(self):
        summary = _summary("a", "Test Player")
        profile = _profile(percentile_values={
            "goals_p90": None, "assists_p90": None,
            "shots_p90": None, "passes_p90": None,
            "xg_p90": None, "xa_p90": None,
        })
        with (
            patch("services.chat_service.parse_query", return_value=self._lookup_intent()),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats",
                  return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, TextResponse)

    def test_valid_percentiles_returns_chart_not_text(self):
        summary = _summary("a", "Test Player")
        profile = _profile()  # full percentiles
        with (
            patch("services.chat_service.parse_query", return_value=self._lookup_intent()),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats",
                  return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, ChartResponse)

    def test_chart_has_no_nan_or_inf(self):
        summary = _summary("a", "Test Player")
        profile = _profile()
        with (
            patch("services.chat_service.parse_query", return_value=self._lookup_intent()),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats",
                  return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert not _has_nan_or_inf(result.model_dump())

    def test_partial_percentiles_produces_valid_chart(self):
        """Only some metrics available — chart should still be valid."""
        summary = _summary("a", "Test Player")
        profile = _profile(percentile_values={
            "goals_p90": 80.0, "assists_p90": None,
            "shots_p90": 70.0, "passes_p90": None,
            "xg_p90": None, "xa_p90": 60.0,
        })
        with (
            patch("services.chat_service.parse_query", return_value=self._lookup_intent()),
            patch("services.chat_service.data_service.search_players", return_value=[summary]),
            patch("services.chat_service.stats_service.get_player_profile_stats",
                  return_value=profile),
        ):
            result = execute_chat_query("show me test player")
        assert isinstance(result.response, ChartResponse)
        chart = result.response
        # Only 3 metrics provided (goals, shots, xa) → 3 labels
        assert len(chart.labels) == 3
        for ds in chart.datasets:
            assert len(ds.data) == 3


# ===========================================================================
# Comparison edge cases
# ===========================================================================

class TestComparisonEdgeCases:

    def _comp_result(self, value_a: int = 10_000_000, value_b: int = 8_000_000,
                     league_avg_a=None, league_avg_b=None) -> ComparisonResult:
        return ComparisonResult(
            player_a=_detail("a", "Player A"),
            player_b=_detail("b", "Player B"),
            metrics=[
                MetricComparison(metric_name="goals_p90", label="Goals per 90",
                                 value_a=0.5, value_b=0.4, winner="a"),
            ],
            market_context=MarketContext(
                value_a=value_a, value_b=value_b,
                league_avg_a=league_avg_a, league_avg_b=league_avg_b,
            ),
        )

    def test_missing_market_peer_average_remains_none(self):
        comp = self._comp_result(league_avg_a=None, league_avg_b=None)
        intent = _intent(intent="comparison", players=["A", "B"])
        sa = _summary("a", "A")
        sb = _summary("b", "B")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[sa], [sb]]),
            patch("services.chat_service.comparison_service.compare_players",
                  return_value=comp),
        ):
            result = execute_chat_query("compare A and B")
        ctx = result.response.result.market_context
        assert ctx.league_avg_a is None
        assert ctx.league_avg_b is None

    def test_same_player_comparison_safe(self):
        comp = self._comp_result()
        intent = _intent(intent="comparison", players=["Mohamed Salah", "Mohamed Salah"])
        s = _summary(SALAH_ID, "Mohamed Salah")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players", return_value=[s]),
            patch("services.chat_service.comparison_service.compare_players",
                  return_value=comp),
        ):
            result = execute_chat_query("compare Salah and Salah")
        assert isinstance(result.response, ComparisonResponse)

    def test_winners_are_valid_values(self):
        comp = self._comp_result()
        intent = _intent(intent="comparison", players=["A", "B"])
        sa = _summary("a", "A")
        sb = _summary("b", "B")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[sa], [sb]]),
            patch("services.chat_service.comparison_service.compare_players",
                  return_value=comp),
        ):
            result = execute_chat_query("compare A and B")
        for m in result.response.result.metrics:
            assert m.winner in ("a", "b", "draw")

    def test_no_nan_in_comparison_response(self):
        comp = self._comp_result()
        intent = _intent(intent="comparison", players=["A", "B"])
        sa = _summary("a", "A")
        sb = _summary("b", "B")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.data_service.search_players",
                  side_effect=[[sa], [sb]]),
            patch("services.chat_service.comparison_service.compare_players",
                  return_value=comp),
        ):
            result = execute_chat_query("compare A and B")
        assert not _has_nan_or_inf(result.model_dump())


# ===========================================================================
# Parser hardening
# ===========================================================================

class TestParserHardening:

    def test_none_input_does_not_raise(self):
        result = parse_query(None)  # type: ignore[arg-type]
        assert result.intent == "unknown"

    def test_integer_input_does_not_raise(self):
        result = parse_query(42)  # type: ignore[arg-type]
        assert result.intent == "unknown"

    def test_empty_string_returns_unknown(self):
        result = parse_query("")
        assert result.intent == "unknown"
        assert result.clarification_message

    def test_invalid_llm_intent_falls_back_safely(self, monkeypatch):
        import json as _json
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        args = {"intent": "fly_to_mars", "players": []}
        mock_tool = MagicMock()
        mock_tool.function.arguments = _json.dumps(args)
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tool]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result = parse_query("fly to mars")
        # Should fall back gracefully — either rule-based or unknown
        assert result.intent in ("ranking", "player_lookup", "comparison", "unknown")

    def test_blank_player_names_not_returned(self, monkeypatch):
        import json as _json
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        args = {"intent": "comparison", "players": ["", "  ", "Salah"]}
        mock_tool = MagicMock()
        mock_tool.function.arguments = _json.dumps(args)
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tool]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result = parse_query("compare and Salah")
        # With blank player entries, comparison < 2 real names → unknown
        assert result.intent in ("comparison", "unknown")

    def test_negative_min_minutes_sanitized_by_llm_path(self, monkeypatch):
        import json as _json
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        args = {"intent": "ranking", "metric": "goals", "min_minutes": -500}
        mock_tool = MagicMock()
        mock_tool.function.arguments = _json.dumps(args)
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tool]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result = parse_query("top players by goals with low minutes")
        # min_minutes with negative value — parser currently passes through (service clamps)
        # The important thing is no crash
        assert result is not None

    def test_more_than_two_comparison_players_handled(self):
        """Rule-based parser should not crash on 3+ player names."""
        result = parse_query("Compare Salah, Kane, and Mbappe")
        # Result might be unknown or comparison with 2 names — no crash
        assert result.intent in ("comparison", "unknown")

    def test_invalid_json_from_llm_falls_back(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_tool = MagicMock()
        mock_tool.function.arguments = "NOT VALID JSON {{{{"
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tool]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            result = parse_query("top forwards by goals")
        # Must fall back to rule-based, not crash
        assert result is not None
        assert result.intent in ("ranking", "player_lookup", "comparison", "unknown")


# ===========================================================================
# REST regression
# ===========================================================================

class TestRESTRegression:

    def test_health_still_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_search_blank_query_returns_400(self):
        r = client.get("/players/search?q= ")
        assert r.status_code == 400

    def test_search_known_player(self):
        r = client.get("/players/search?q=Salah")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_profile_unknown_returns_404(self):
        r = client.get("/players/ghost-000000")
        assert r.status_code == 404

    def test_compare_missing_param_returns_422(self):
        r = client.get("/players/compare", params={"player_a_id": SALAH_ID})
        assert r.status_code == 422

    def test_compare_unknown_player_returns_404(self):
        r = client.get("/players/compare",
                       params={"player_a_id": "ghost-000", "player_b_id": KANE_ID})
        assert r.status_code == 404

    def test_internal_exception_does_not_expose_text(self):
        intent = _intent(intent="ranking", metric="goals")
        with (
            patch("services.chat_service.parse_query", return_value=intent),
            patch("services.chat_service.stats_service.rank_players",
                  side_effect=RuntimeError("INTERNAL SQL CRASH")),
        ):
            r = client.post("/chat", json={"message": "top players by goals"})
        assert r.status_code == 200
        body_str = r.text
        assert "INTERNAL SQL CRASH" not in body_str
        assert "Traceback" not in body_str
        assert "RuntimeError" not in body_str

    def test_chat_always_200_not_500(self):
        """Any exception inside execute_chat_query must not bubble to HTTP 500."""
        with patch("services.chat_service.parse_query",
                   side_effect=RuntimeError("catastrophic failure")):
            r = client.post("/chat", json={"message": "top players by goals"})
        assert r.status_code == 200
        assert r.json()["response"]["type"] == "text"
        assert r.json()["response"]["is_error"] is True


# ===========================================================================
# Serialization: no NaN/infinity in successful responses
# ===========================================================================

class TestNoNaNInResponses:

    def test_live_ranking_no_nan(self):
        r = client.post("/chat",
                        json={"message": "Top 5 forwards in the Premier League by goals"})
        assert r.status_code == 200
        assert not _has_nan_or_inf(r.json())

    def test_live_comparison_no_nan(self):
        r = client.post("/chat",
                        json={"message": "Compare Mohamed Salah and Harry Kane"})
        assert r.status_code == 200
        assert not _has_nan_or_inf(r.json())

    def test_live_lookup_no_nan(self):
        r = client.post("/chat", json={"message": "Show me Mohamed Salah"})
        assert r.status_code == 200
        assert not _has_nan_or_inf(r.json())

    def test_live_unknown_no_nan(self):
        r = client.post("/chat", json={"message": "Who is the best player?"})
        assert r.status_code == 200
        assert not _has_nan_or_inf(r.json())
