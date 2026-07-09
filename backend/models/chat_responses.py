"""
Chat response models — discriminated union returned by POST /chat.

The frontend switches on `response.type` to pick the correct renderer:
    "table"      → render as an HTML table
    "chart"      → render as a Recharts BarChart or RadarChart
    "comparison" → render the ComparisonChart component (View 3 reuse)
    "text"       → render as prose; is_error=True shows an error box

ParsedIntent is also defined here because it is purely a chat-layer
concern (NLU output → intent dispatch input).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from models.player import ComparisonResult


# ---------------------------------------------------------------------------
# NLU
# ---------------------------------------------------------------------------


class ParsedIntent(BaseModel):
    intent: Literal["ranking", "lookup", "comparison", "unknown"]
    players: list[str] = Field(default_factory=list)
    metric: str | None = None
    league: str | None = None
    position: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    limit: int = 5
    raw_query: str = ""


# ---------------------------------------------------------------------------
# Response leaf types
# ---------------------------------------------------------------------------


class ChartDataset(BaseModel):
    label: str
    data: list[float]
    color: str | None = None


class ChartResponse(BaseModel):
    type: Literal["chart"] = "chart"
    title: str
    chart_type: Literal["bar", "radar", "line"] = "bar"
    labels: list[str]
    datasets: list[ChartDataset]


class TableResponse(BaseModel):
    type: Literal["table"] = "table"
    title: str
    columns: list[str]
    rows: list[dict]


class ComparisonResponse(BaseModel):
    type: Literal["comparison"] = "comparison"
    result: ComparisonResult


class TextResponse(BaseModel):
    type: Literal["text"] = "text"
    message: str
    is_error: bool = False


# ---------------------------------------------------------------------------
# Discriminated union — what POST /chat always returns
# ---------------------------------------------------------------------------

ResponseUnion = Annotated[
    ChartResponse | TableResponse | ComparisonResponse | TextResponse,
    Field(discriminator="type"),
]


class ChatResponse(BaseModel):
    response: ResponseUnion
