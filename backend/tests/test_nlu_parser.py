"""
tests/test_nlu_parser.py — unit tests for nlu/parser.py

All tests must pass without an OPENAI_API_KEY.
OpenAI tests use mocks; no real API calls are ever made.

Run from backend/:
    pytest tests/test_nlu_parser.py
"""

from __future__ import annotations

import ast
import inspect
import json
import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(text: str):
    """Import-fresh parse_query using env isolation (no API key)."""
    from nlu.parser import parse_query
    return parse_query(text)


@pytest.fixture(autouse=True)
def no_openai_key(monkeypatch):
    """Ensure no real OPENAI_API_KEY leaks into tests."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ===========================================================================
# General
# ===========================================================================

class TestGeneral:

    def test_blank_query_returns_unknown(self):
        result = _parse("")
        assert result.intent == "unknown"

    def test_whitespace_only_returns_unknown(self):
        result = _parse("   ")
        assert result.intent == "unknown"

    def test_blank_has_clarification_message(self):
        result = _parse("")
        assert result.clarification_message is not None
        assert len(result.clarification_message) > 0

    def test_never_raises_on_garbage_input(self):
        garbage = ["???", "12345!@#", "<script>alert(1)</script>", "a" * 5000, "\x00\x01\x02"]
        for text in garbage:
            result = _parse(text)
            assert result.intent in ("ranking", "player_lookup", "comparison", "unknown")

    def test_no_api_key_uses_fallback(self, monkeypatch):
        """Without OPENAI_API_KEY, rule-based parser runs and returns a result."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = _parse("Top 5 forwards in the Premier League by goals")
        assert result.intent == "ranking"
        assert result.metric == "goals"

    def test_parser_has_no_service_imports(self):
        """parser.py must not import from services/ or routers/."""
        import nlu.parser as parser_module
        source = inspect.getsource(parser_module)
        tree = ast.parse(source)
        forbidden_prefixes = ("services", "routers")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for prefix in forbidden_prefixes:
                    assert not node.module.startswith(prefix), (
                        f"parser.py imports from forbidden module: {node.module}"
                    )

    def test_raw_query_preserved(self):
        text = "Top 5 forwards by goals"
        result = _parse(text)
        assert result.raw_query == text


# ===========================================================================
# Ranking
# ===========================================================================

class TestRanking:

    def test_top5_wingers_under23_pl_by_assists(self):
        result = _parse("Top 5 wingers under 23 in the Premier League by assists")
        assert result.intent == "ranking"
        assert result.position == "FWD"
        assert result.league == "Premier League"
        assert result.metric == "assists"
        assert result.limit == 5
        assert result.max_age == 23

    def test_best_forwards_la_liga_by_goals(self):
        result = _parse("Best 10 forwards in La Liga by goals")
        assert result.intent == "ranking"
        assert result.position == "FWD"
        assert result.league == "La Liga"
        assert result.metric == "goals"
        assert result.limit == 10

    def test_top_midfielders_by_xg(self):
        result = _parse("Top midfielders by xG")
        assert result.intent == "ranking"
        assert result.position == "MID"
        assert result.metric == "xg"

    def test_ranking_without_metric_returns_unknown(self):
        result = _parse("Top 5 forwards in the Premier League")
        assert result.intent == "unknown"
        assert result.clarification_message is not None
        assert "metric" in result.clarification_message.lower() or "rank" in result.clarification_message.lower() or "goals" in result.clarification_message.lower()

    def test_limit_extracted(self):
        result = _parse("Top 10 strikers by goals")
        assert result.limit == 10

    def test_limit_clamped_to_50(self):
        result = _parse("Top 999 strikers by goals")
        assert result.limit == 50

    def test_max_age_extracted(self):
        result = _parse("Best forwards under 25 by xG")
        assert result.max_age == 25

    def test_min_age_extracted(self):
        result = _parse("Top midfielders over 30 by passes")
        assert result.intent == "ranking"
        assert result.min_age == 30

    def test_epl_alias_normalises(self):
        result = _parse("Top 5 strikers in the EPL by goals")
        assert result.league == "Premier League"

    def test_pl_alias_normalises(self):
        result = _parse("Top 5 strikers in the PL by goals")
        assert result.league == "Premier League"

    def test_winger_normalises_to_fwd(self):
        result = _parse("Top 5 wingers by assists")
        assert result.position == "FWD"

    def test_striker_normalises_to_fwd(self):
        result = _parse("Best strikers in Serie A by xG")
        assert result.position == "FWD"

    def test_midfielder_normalises_to_mid(self):
        result = _parse("Top midfielders by passes")
        assert result.position == "MID"

    def test_goalkeeper_normalises_to_gk(self):
        result = _parse("Top goalkeepers in the Bundesliga by minutes")
        assert result.position == "GK"

    def test_total_goals_maps_to_goals_total(self):
        result = _parse("Top 5 forwards by total goals")
        assert result.metric == "goals_total"

    def test_goals_per_90_maps_to_goals_p90(self):
        result = _parse("Best forwards by goals per 90")
        assert result.metric == "goals_p90"

    def test_goals_maps_to_goals(self):
        result = _parse("Top forwards in the Premier League by goals")
        assert result.metric == "goals"

    def test_la_liga_alias(self):
        result = _parse("Top 5 forwards in La Liga by xg")
        assert result.league == "La Liga"

    def test_spanish_league_alias(self):
        result = _parse("Top 5 forwards in the Spanish league by goals")
        assert result.league == "La Liga"

    def test_bundesliga_alias(self):
        result = _parse("Top midfielders in the German league by passes")
        assert result.league == "Bundesliga"

    def test_ligue1_alias(self):
        result = _parse("Top forwards in Ligue 1 by goals")
        assert result.league == "Ligue 1"


# ===========================================================================
# Comparison
# ===========================================================================

class TestComparison:

    def test_compare_salah_and_kane(self):
        result = _parse("Compare Salah and Kane")
        assert result.intent == "comparison"
        assert len(result.players) == 2

    def test_compare_salah_and_kane_names(self):
        result = _parse("Compare Salah and Kane")
        names_lower = [p.lower() for p in result.players]
        assert any("salah" in n for n in names_lower)
        assert any("kane" in n for n in names_lower)

    def test_salah_vs_kane(self):
        result = _parse("Salah vs Kane")
        assert result.intent == "comparison"
        assert len(result.players) == 2

    def test_versus_variant(self):
        result = _parse("Salah versus Kane")
        assert result.intent == "comparison"

    def test_who_is_better(self):
        result = _parse("Who is better, Salah or Kane?")
        assert result.intent == "comparison"
        assert len(result.players) == 2

    def test_one_player_compare_returns_unknown(self):
        result = _parse("Compare Salah")
        assert result.intent == "unknown"
        assert result.clarification_message is not None

    def test_exactly_two_players_returned(self):
        result = _parse("Compare Salah and Kane")
        assert result.intent == "comparison"
        assert len(result.players) == 2

    def test_full_names(self):
        result = _parse("Compare Mohamed Salah and Harry Kane")
        assert result.intent == "comparison"
        assert len(result.players) == 2


# ===========================================================================
# Player lookup
# ===========================================================================

class TestLookup:

    def test_show_me_salah(self):
        result = _parse("Show me Mohamed Salah")
        assert result.intent == "player_lookup"
        assert any("salah" in p.lower() for p in result.players)

    def test_tell_me_about_kane(self):
        result = _parse("Tell me about Harry Kane")
        assert result.intent == "player_lookup"
        assert any("kane" in p.lower() for p in result.players)

    def test_average_position_comparison_is_lookup(self):
        result = _parse("How does Mohamed Salah compare to the average forward in the Premier League?")
        assert result.intent == "player_lookup"

    def test_who_is_player(self):
        result = _parse("Who is Harry Kane?")
        assert result.intent == "player_lookup"

    def test_player_league_extracted_in_lookup(self):
        result = _parse("Show me Mohamed Salah in the Premier League")
        assert result.league == "Premier League"

    def test_show_me_salah_in_pl_name_only(self):
        result = _parse("Show me Mohamed Salah in the Premier League")
        assert result.intent == "player_lookup"
        assert len(result.players) == 1
        assert "salah" in result.players[0].lower()
        assert "premier" not in result.players[0].lower()

    def test_tell_me_about_kane_from_pl_name_only(self):
        result = _parse("Tell me about Harry Kane from the Premier League")
        assert result.intent == "player_lookup"
        assert len(result.players) == 1
        assert "kane" in result.players[0].lower()
        assert "premier" not in result.players[0].lower()

    def test_show_me_salah_by_xg_name_only(self):
        result = _parse("Show me Mohamed Salah by xG")
        assert result.intent == "player_lookup"
        assert len(result.players) == 1
        assert "salah" in result.players[0].lower()
        # "by xG" must NOT be part of the player name
        assert "xg" not in result.players[0].lower()


# ===========================================================================
# Unknown
# ===========================================================================

class TestUnknown:

    def test_out_of_scope_query(self):
        result = _parse("Tell me about football history")
        assert result.intent == "unknown"

    def test_vague_best_player(self):
        result = _parse("Who is the best player?")
        assert result.intent == "unknown"

    def test_future_prediction(self):
        result = _parse("What will happen next season?")
        assert result.intent == "unknown"

    def test_vague_ranking_no_metric(self):
        result = _parse("Top players in the Premier League")
        # No metric → unknown or, if detected as ranking, clarification message
        if result.intent == "unknown":
            assert True
        else:
            assert result.clarification_message is not None

    def test_clarification_populated_for_blank(self):
        result = _parse("")
        assert result.clarification_message is not None

    def test_clarification_populated_for_one_player_compare(self):
        result = _parse("Compare Salah")
        assert result.clarification_message is not None

    def test_clarification_populated_for_ranking_without_metric(self):
        result = _parse("Top 5 forwards in the Premier League")
        assert result.intent == "unknown"
        assert result.clarification_message is not None


# ===========================================================================
# OpenAI integration (mock-only — no real API calls)
# ===========================================================================

class TestLLMIntegration:

    def _make_mock_client(self, arguments: dict):
        """Build a MagicMock mimicking the OpenAI response structure."""
        mock_tool_call = MagicMock()
        mock_tool_call.function.arguments = json.dumps(arguments)

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_valid_structured_response_parses(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {
            "intent": "ranking",
            "players": [],
            "metric": "goals",
            "position": "FWD",
            "league": "Premier League",
            "limit": 5,
            "max_age": 23,
        }
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Top 5 forwards under 23 by goals")
        assert result.intent == "ranking"
        assert result.metric == "goals"
        assert result.position == "FWD"
        assert result.league == "Premier League"
        assert result.limit == 5
        assert result.max_age == 23

    def test_invalid_json_falls_back_to_rule_based(self, monkeypatch):
        """Malformed JSON from the model should fall back to rule-based parser."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        mock_tool_call = MagicMock()
        mock_tool_call.function.arguments = "NOT VALID JSON {{{"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            # Rule-based fallback should not raise
            result = parse_query("Top 5 forwards by goals")
        assert result.intent in ("ranking", "unknown")

    def test_api_exception_falls_back(self, monkeypatch):
        """An exception from the OpenAI client should fall back gracefully."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("Network error")

        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Top 5 forwards by goals")
        # Fell back to rule-based
        assert result.intent in ("ranking", "unknown")

    def test_limit_clamped_on_llm_output(self, monkeypatch):
        """LLM returning limit > MAX_LIMIT is clamped."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {"intent": "ranking", "players": [], "metric": "goals", "limit": 999}
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Top 999 forwards by goals")
        assert result.limit == 50

    def test_no_real_api_call_without_key(self, monkeypatch):
        """Without OPENAI_API_KEY, OpenAI is never instantiated."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("nlu.parser.OpenAI") as mock_openai_cls:
            from nlu.parser import parse_query
            parse_query("Top 5 forwards by goals")
        mock_openai_cls.assert_not_called()


# ===========================================================================
# _validate_intent_result — shared post-validation
# ===========================================================================

class TestValidateIntentResult:

    def test_unknown_without_clarification_gets_default(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {"intent": "unknown"}
        mock_client = self._make_mock_client(args)  # type: ignore[attr-defined]
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("some vague football question")
        assert result.intent == "unknown"
        assert result.clarification_message is not None
        assert len(result.clarification_message) > 0

    def _make_mock_client(self, arguments: dict):
        mock_tool_call = MagicMock()
        mock_tool_call.function.arguments = json.dumps(arguments)
        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_comparison_one_player_becomes_unknown(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {"intent": "comparison", "players": ["Salah"]}
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Compare Salah")
        assert result.intent == "unknown"
        assert "two" in result.clarification_message.lower() or "player" in result.clarification_message.lower()

    def test_ranking_no_metric_becomes_unknown(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {"intent": "ranking", "players": [], "position": "FWD", "league": "Premier League"}
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Top forwards in the Premier League")
        assert result.intent == "unknown"
        assert "metric" in result.clarification_message.lower() or "goals" in result.clarification_message.lower()

    def test_lookup_no_player_becomes_unknown(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {"intent": "player_lookup", "players": []}
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Show me a player")
        assert result.intent == "unknown"
        assert "player" in result.clarification_message.lower()

    def test_valid_ranking_unchanged(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {
            "intent": "ranking", "players": [], "metric": "goals",
            "position": "FWD", "league": "Premier League", "limit": 5,
        }
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Top 5 forwards in the PL by goals")
        assert result.intent == "ranking"
        assert result.metric == "goals"

    def test_valid_comparison_unchanged(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {"intent": "comparison", "players": ["Salah", "Kane"]}
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Compare Salah and Kane")
        assert result.intent == "comparison"
        assert len(result.players) == 2

    def test_valid_lookup_unchanged(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        args = {"intent": "player_lookup", "players": ["Mohamed Salah"]}
        mock_client = self._make_mock_client(args)
        with patch("nlu.parser.OpenAI", return_value=mock_client):
            from nlu.parser import parse_query
            result = parse_query("Show me Mohamed Salah")
        assert result.intent == "player_lookup"
        assert result.players[0] == "Mohamed Salah"
