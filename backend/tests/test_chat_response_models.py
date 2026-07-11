"""
Tests for backend/models/chat_responses.py

Covers:
    - ChatRequest validation
    - TextResponse validation
    - TableResponse validation
    - ChartDataset / ChartResponse validation
    - ComparisonResponse validation
    - Discriminated-union ChatResponse dispatch
    - OpenAPI schema generation
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from models.chat_responses import (
    ChatRequest,
    ChatResponse,
    ChartDataset,
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
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _player_detail(player_id: str = "aaa00001", name: str = "Player A") -> PlayerDetail:
    return PlayerDetail(
        player_id=player_id,
        name=name,
        position="FWD",
        club="FC Test",
        league="Premier League",
        market_value_eur=20_000_000,
        age=25,
        goals=10,
        assists=5,
        minutes_played=1800,
        shots=50,
        passes=300,
        xg=8.5,
        xa=4.2,
    )


def _comparison_result() -> ComparisonResult:
    return ComparisonResult(
        player_a=_player_detail("aaa00001", "Player A"),
        player_b=_player_detail("bbb00002", "Player B"),
        metrics=[
            MetricComparison(
                metric_name="goals_p90",
                label="Goals per 90",
                value_a=0.5,
                value_b=0.4,
                winner="a",
            )
        ],
        market_context=MarketContext(
            value_a=20_000_000,
            value_b=15_000_000,
            league_avg_a=18_000_000,
            league_avg_b=16_000_000,
        ),
    )


# ===========================================================================
# ChatRequest
# ===========================================================================


class TestChatRequest:
    def test_valid_message(self):
        req = ChatRequest(message="Top 5 forwards by goals")
        assert req.message == "Top 5 forwards by goals"

    def test_leading_trailing_whitespace_trimmed(self):
        req = ChatRequest(message="  Top 5 forwards  ")
        assert req.message == "Top 5 forwards"

    def test_blank_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="   ")

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_message_at_max_length_accepted(self):
        msg = "x" * 1000
        req = ChatRequest(message=msg)
        assert len(req.message) == 1000

    def test_message_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="x" * 1001)

    def test_single_character_message(self):
        req = ChatRequest(message="?")
        assert req.message == "?"


# ===========================================================================
# TextResponse
# ===========================================================================


class TestTextResponse:
    def test_valid_text_response(self):
        r = TextResponse(message="Hello there")
        assert r.type == "text"
        assert r.message == "Hello there"
        assert r.is_error is False

    def test_type_is_always_text(self):
        r = TextResponse(message="ok")
        assert r.type == "text"

    def test_is_error_flag(self):
        r = TextResponse(message="Something went wrong", is_error=True)
        assert r.is_error is True

    def test_blank_message_rejected(self):
        with pytest.raises(ValidationError):
            TextResponse(message="")

    def test_whitespace_only_message_rejected(self):
        with pytest.raises(ValidationError):
            TextResponse(message="   ")

    def test_serialization(self):
        data = TextResponse(message="Clarify?", is_error=True).model_dump()
        assert data == {"type": "text", "message": "Clarify?", "is_error": True}


# ===========================================================================
# TableResponse
# ===========================================================================


class TestTableResponse:
    def _valid_table(self) -> TableResponse:
        return TableResponse(
            title="Top forwards",
            columns=["rank", "name", "value"],
            rows=[{"rank": 1, "name": "Salah", "value": 0.79}],
        )

    def test_valid_table(self):
        t = self._valid_table()
        assert t.type == "table"
        assert t.title == "Top forwards"

    def test_empty_rows_allowed(self):
        t = TableResponse(title="Empty", columns=["name"], rows=[])
        assert t.rows == []

    def test_blank_title_rejected(self):
        with pytest.raises(ValidationError):
            TableResponse(title="", columns=["name"], rows=[])

    def test_empty_columns_rejected(self):
        with pytest.raises(ValidationError):
            TableResponse(title="T", columns=[], rows=[])

    def test_duplicate_columns_rejected(self):
        with pytest.raises(ValidationError):
            TableResponse(
                title="T",
                columns=["name", "name"],
                rows=[],
            )

    def test_row_missing_declared_column_rejected(self):
        with pytest.raises(ValidationError):
            TableResponse(
                title="T",
                columns=["rank", "name", "value"],
                rows=[{"rank": 1, "name": "Salah"}],  # missing "value"
            )

    def test_extra_row_keys_allowed(self):
        """Extra keys beyond declared columns are permitted."""
        t = TableResponse(
            title="T",
            columns=["name"],
            rows=[{"name": "Salah", "extra_field": 42}],
        )
        assert t.rows[0]["extra_field"] == 42

    def test_serialization(self):
        data = self._valid_table().model_dump()
        assert data["type"] == "table"
        assert data["columns"] == ["rank", "name", "value"]
        assert data["rows"][0]["name"] == "Salah"

    def test_incorrect_discriminator_rejected(self):
        with pytest.raises(ValidationError):
            TableResponse(type="wrong", title="T", columns=["x"], rows=[])  # type: ignore[arg-type]


# ===========================================================================
# ChartDataset
# ===========================================================================


class TestChartDataset:
    def test_valid_dataset(self):
        ds = ChartDataset(label="Salah", data=[0.5, 0.8, 0.7])
        assert ds.label == "Salah"

    def test_blank_label_rejected(self):
        with pytest.raises(ValidationError):
            ChartDataset(label="", data=[1.0])

    def test_nan_rejected(self):
        with pytest.raises(ValidationError):
            ChartDataset(label="ds", data=[float("nan")])

    def test_positive_infinity_rejected(self):
        with pytest.raises(ValidationError):
            ChartDataset(label="ds", data=[float("inf")])

    def test_negative_infinity_rejected(self):
        with pytest.raises(ValidationError):
            ChartDataset(label="ds", data=[float("-inf")])

    def test_nan_in_list_rejected(self):
        with pytest.raises(ValidationError):
            ChartDataset(label="ds", data=[1.0, math.nan, 3.0])

    def test_zero_and_negatives_accepted(self):
        ds = ChartDataset(label="ds", data=[-1.0, 0.0, 100.0])
        assert ds.data == [-1.0, 0.0, 100.0]

    def test_no_color_field(self):
        """color was removed from ChartDataset."""
        ds = ChartDataset(label="ds", data=[1.0])
        assert not hasattr(ds, "color")


# ===========================================================================
# ChartResponse
# ===========================================================================


class TestChartResponse:
    def _bar_chart(self) -> ChartResponse:
        return ChartResponse(
            title="Goals comparison",
            labels=["Goals", "Assists", "xG"],
            datasets=[ChartDataset(label="Salah", data=[0.79, 0.3, 0.72])],
        )

    def _radar_chart(self) -> ChartResponse:
        return ChartResponse(
            title="Radar",
            chart_type="radar",
            labels=["G", "A"],
            datasets=[
                ChartDataset(label="Player A", data=[80.0, 60.0]),
                ChartDataset(label="Player B", data=[50.0, 70.0]),
            ],
        )

    def test_valid_bar_chart(self):
        c = self._bar_chart()
        assert c.chart_type == "bar"
        assert c.type == "chart"

    def test_valid_radar_chart(self):
        c = self._radar_chart()
        assert c.chart_type == "radar"

    def test_default_chart_type_is_bar(self):
        c = ChartResponse(
            title="T",
            labels=["x"],
            datasets=[ChartDataset(label="d", data=[1.0])],
        )
        assert c.chart_type == "bar"

    def test_blank_title_rejected(self):
        with pytest.raises(ValidationError):
            ChartResponse(
                title="",
                labels=["x"],
                datasets=[ChartDataset(label="d", data=[1.0])],
            )

    def test_empty_labels_rejected(self):
        with pytest.raises(ValidationError):
            ChartResponse(
                title="T",
                labels=[],
                datasets=[ChartDataset(label="d", data=[])],
            )

    def test_empty_datasets_rejected(self):
        with pytest.raises(ValidationError):
            ChartResponse(title="T", labels=["x"], datasets=[])

    def test_mismatched_dataset_length_rejected(self):
        with pytest.raises(ValidationError):
            ChartResponse(
                title="T",
                labels=["A", "B", "C"],
                datasets=[ChartDataset(label="d", data=[1.0, 2.0])],  # 2 ≠ 3
            )

    def test_multiple_datasets_all_must_match(self):
        with pytest.raises(ValidationError):
            ChartResponse(
                title="T",
                labels=["A", "B"],
                datasets=[
                    ChartDataset(label="ok", data=[1.0, 2.0]),
                    ChartDataset(label="bad", data=[1.0]),  # wrong length
                ],
            )

    def test_nan_in_dataset_rejected(self):
        with pytest.raises(ValidationError):
            ChartResponse(
                title="T",
                labels=["A"],
                datasets=[ChartDataset(label="d", data=[float("nan")])],
            )

    def test_serialization(self):
        data = self._bar_chart().model_dump()
        assert data["type"] == "chart"
        assert data["chart_type"] == "bar"
        assert data["labels"] == ["Goals", "Assists", "xG"]
        assert data["datasets"][0]["label"] == "Salah"


# ===========================================================================
# ComparisonResponse
# ===========================================================================


class TestComparisonResponse:
    def test_valid_comparison_response(self):
        r = ComparisonResponse(result=_comparison_result())
        assert r.type == "comparison"
        assert r.result.player_a.name == "Player A"

    def test_type_is_always_comparison(self):
        r = ComparisonResponse(result=_comparison_result())
        assert r.type == "comparison"

    def test_serialization_contains_result_key(self):
        data = ComparisonResponse(result=_comparison_result()).model_dump()
        assert "result" in data
        assert data["result"]["player_a"]["name"] == "Player A"


# ===========================================================================
# ChatResponse — discriminated union dispatch
# ===========================================================================


class TestChatResponseDiscriminator:
    def test_selects_text_response(self):
        cr = ChatResponse(response={"type": "text", "message": "hi"})
        assert isinstance(cr.response, TextResponse)

    def test_selects_table_response(self):
        cr = ChatResponse(
            response={
                "type": "table",
                "title": "Rankings",
                "columns": ["name"],
                "rows": [],
            }
        )
        assert isinstance(cr.response, TableResponse)

    def test_selects_chart_response(self):
        cr = ChatResponse(
            response={
                "type": "chart",
                "title": "Chart",
                "labels": ["A"],
                "datasets": [{"label": "ds", "data": [1.0]}],
            }
        )
        assert isinstance(cr.response, ChartResponse)

    def test_selects_comparison_response(self):
        result_dict = _comparison_result().model_dump()
        cr = ChatResponse(response={"type": "comparison", "result": result_dict})
        assert isinstance(cr.response, ComparisonResponse)

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            ChatResponse(response={"type": "unknown_type", "message": "x"})

    def test_missing_type_rejected(self):
        with pytest.raises(ValidationError):
            ChatResponse(response={"message": "hi"})

    def test_text_response_round_trip(self):
        original = ChatResponse(
            response=TextResponse(message="test", is_error=False)
        )
        data = original.model_dump()
        restored = ChatResponse(**data)
        assert isinstance(restored.response, TextResponse)
        assert restored.response.message == "test"

    def test_table_response_round_trip(self):
        original = ChatResponse(
            response=TableResponse(
                title="T",
                columns=["name", "goals"],
                rows=[{"name": "Salah", "goals": 22}],
            )
        )
        data = original.model_dump()
        restored = ChatResponse(**data)
        assert isinstance(restored.response, TableResponse)

    def test_chart_response_round_trip(self):
        original = ChatResponse(
            response=ChartResponse(
                title="C",
                labels=["G"],
                datasets=[ChartDataset(label="d", data=[1.0])],
            )
        )
        data = original.model_dump()
        restored = ChatResponse(**data)
        assert isinstance(restored.response, ChartResponse)


# ===========================================================================
# OpenAPI schema generation
# ===========================================================================


class TestOpenAPISchema:
    def test_main_app_openapi_generates_without_error(self):
        """Importing and calling main.app.openapi() must not raise."""
        import sys
        import os
        # Ensure the backend root is on the path
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        from main import app
        schema = app.openapi()
        assert isinstance(schema, dict)

    def test_chat_response_has_all_four_variants(self):
        import sys
        import os
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        from main import app
        schema = app.openapi()
        schema_str = str(schema)
        for variant in ("TextResponse", "TableResponse", "ChartResponse", "ComparisonResponse"):
            assert variant in schema_str, f"{variant} not found in OpenAPI schema"


# ===========================================================================
# Whitespace stripping and non-blank validation
# ===========================================================================


class TestWhitespaceValidation:
    """Verify that whitespace-only values are rejected and valid values are stripped."""

    # --- TableResponse.title ---

    def test_table_whitespace_title_rejected(self):
        with pytest.raises(ValidationError):
            TableResponse(title=" ", columns=["name"], rows=[])

    def test_table_title_stripped(self):
        t = TableResponse(title="  Players  ", columns=["name"], rows=[])
        assert t.title == "Players"

    # --- TableResponse.columns ---

    def test_table_whitespace_column_rejected(self):
        with pytest.raises(ValidationError):
            TableResponse(title="T", columns=[" "], rows=[])

    def test_table_column_stripped(self):
        t = TableResponse(title="T", columns=["  name  "], rows=[])
        assert t.columns == ["name"]

    def test_table_stripped_duplicate_columns_rejected(self):
        """['name', ' name '] strips to ['name', 'name'] → duplicate → rejected."""
        with pytest.raises(ValidationError):
            TableResponse(title="T", columns=["name", " name "], rows=[])

    def test_table_row_keys_aligned_with_stripped_columns(self):
        """Row keys must match stripped column names, not raw names."""
        t = TableResponse(
            title="T",
            columns=["  rank  ", "  name  "],
            rows=[{"rank": 1, "name": "Salah"}],
        )
        assert t.columns == ["rank", "name"]

    # --- ChartResponse.title ---

    def test_chart_whitespace_title_rejected(self):
        with pytest.raises(ValidationError):
            ChartResponse(
                title=" ",
                labels=["Goals"],
                datasets=[ChartDataset(label="Player", data=[1.0])],
            )

    def test_chart_title_stripped(self):
        c = ChartResponse(
            title="  My Chart  ",
            labels=["Goals"],
            datasets=[ChartDataset(label="Player", data=[1.0])],
        )
        assert c.title == "My Chart"

    # --- ChartResponse.labels ---

    def test_chart_whitespace_label_rejected(self):
        with pytest.raises(ValidationError):
            ChartResponse(
                title="Chart",
                labels=[" "],
                datasets=[ChartDataset(label="Player", data=[1.0])],
            )

    def test_chart_label_stripped(self):
        c = ChartResponse(
            title="Chart",
            labels=["  Goals  "],
            datasets=[ChartDataset(label="Player", data=[1.0])],
        )
        assert c.labels == ["Goals"]

    def test_chart_mixed_labels_stripped(self):
        c = ChartResponse(
            title="Chart",
            labels=["  Goals  ", " Assists ", "xG"],
            datasets=[ChartDataset(label="d", data=[1.0, 2.0, 3.0])],
        )
        assert c.labels == ["Goals", "Assists", "xG"]

    # --- ChartDataset.label ---

    def test_dataset_whitespace_label_rejected(self):
        with pytest.raises(ValidationError):
            ChartDataset(label="   ", data=[1.0])

    def test_dataset_label_stripped(self):
        ds = ChartDataset(label="  Salah  ", data=[1.0])
        assert ds.label == "Salah"
