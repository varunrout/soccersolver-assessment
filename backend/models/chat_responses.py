"""
Chat response models — discriminated union returned by POST /chat.

The frontend switches on `response.type` to pick the correct renderer:
    "text"       → render as prose; is_error=True shows an error box
    "table"      → render as an HTML table
    "chart"      → render as a Recharts BarChart or RadarChart
    "comparison" → render the ComparisonChart component (View 3 reuse)

ParsedIntent is also defined here because it is purely a chat-layer
concern (NLU output → intent dispatch input).
"""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from models.player import ComparisonResult


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_nonempty(v: Any) -> Any:
    """Strip surrounding whitespace; returned to the field validator."""
    if isinstance(v, str):
        return v.strip()
    return v


def _strip_list_nonempty(items: list[Any], field_name: str) -> list[str]:
    """Strip each string item; raise if any becomes blank after stripping."""
    result: list[str] = []
    for i, item in enumerate(items):
        if isinstance(item, str):
            stripped = item.strip()
            if not stripped:
                raise ValueError(
                    f"{field_name}[{i}] must not be blank"
                )
            result.append(stripped)
        else:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# NLU
# ---------------------------------------------------------------------------


class ParsedIntent(BaseModel):
    intent: Literal["ranking", "player_lookup", "comparison", "unknown"]
    players: list[str] = Field(default_factory=list)
    metric: str | None = None
    league: str | None = None
    position: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_minutes: int | None = None
    limit: int | None = None
    clarification_message: str | None = None
    raw_query: str = ""


# ---------------------------------------------------------------------------
# Chat request
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Incoming message from the user to POST /chat."""

    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


# ---------------------------------------------------------------------------
# Response leaf types
# ---------------------------------------------------------------------------


class TextResponse(BaseModel):
    type: Literal["text"] = "text"
    message: str = Field(min_length=1)
    is_error: bool = False

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, v: Any) -> Any:
        return _strip_nonempty(v)


class TableResponse(BaseModel):
    type: Literal["table"] = "table"
    title: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)
    rows: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, v: Any) -> Any:
        return _strip_nonempty(v)

    @field_validator("columns", mode="before")
    @classmethod
    def _strip_columns(cls, v: Any) -> Any:
        if isinstance(v, list):
            return _strip_list_nonempty(v, "columns")
        return v

    @model_validator(mode="after")
    def _validate_columns_and_rows(self) -> "TableResponse":
        if len(self.columns) != len(set(self.columns)):
            raise ValueError("columns must be unique")
        col_set = set(self.columns)
        for i, row in enumerate(self.rows):
            missing = col_set - set(row.keys())
            if missing:
                raise ValueError(
                    f"row {i} is missing declared column(s): {sorted(missing)}"
                )
        return self


class ChartDataset(BaseModel):
    label: str = Field(min_length=1)
    data: list[float]

    @field_validator("label", mode="before")
    @classmethod
    def _strip_label(cls, v: Any) -> Any:
        return _strip_nonempty(v)

    @field_validator("data")
    @classmethod
    def _reject_non_finite(cls, v: list[float]) -> list[float]:
        for x in v:
            if math.isnan(x) or math.isinf(x):
                raise ValueError(
                    "data must not contain NaN or infinite values"
                )
        return v


class ChartResponse(BaseModel):
    type: Literal["chart"] = "chart"
    title: str = Field(min_length=1)
    chart_type: Literal["bar", "radar", "line"] = "bar"
    labels: list[str] = Field(min_length=1)
    datasets: list[ChartDataset] = Field(min_length=1)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, v: Any) -> Any:
        return _strip_nonempty(v)

    @field_validator("labels", mode="before")
    @classmethod
    def _strip_labels(cls, v: Any) -> Any:
        if isinstance(v, list):
            return _strip_list_nonempty(v, "labels")
        return v

    @model_validator(mode="after")
    def _validate_dataset_lengths(self) -> "ChartResponse":
        n = len(self.labels)
        for ds in self.datasets:
            if len(ds.data) != n:
                raise ValueError(
                    f"dataset '{ds.label}' has {len(ds.data)} data point(s) "
                    f"but there are {n} label(s)"
                )
        return self


class ComparisonResponse(BaseModel):
    type: Literal["comparison"] = "comparison"
    result: ComparisonResult


# ---------------------------------------------------------------------------
# Discriminated union — what POST /chat always returns
# ---------------------------------------------------------------------------

ResponseUnion = Annotated[
    TextResponse | TableResponse | ChartResponse | ComparisonResponse,
    Field(discriminator="type"),
]


class ChatResponse(BaseModel):
    response: ResponseUnion
