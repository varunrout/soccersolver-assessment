"""
routers/chat.py — POST /chat

Three-layer architecture (implemented in Issues #9, #10, #11):
    Layer 1  nlu/parser.py          parse_query(text) → ParsedIntent
    Layer 2  services/*             execute intent using existing services
    Layer 3  routers/chat.py        receive → dispatch → respond

This router contains ZERO business logic.

Implemented fully in Issue #11.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from models.chat_responses import ChatResponse, TextResponse

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("", response_model=ChatResponse, summary="Conversational analytics query")
def chat(request: ChatRequest) -> ChatResponse:
    """
    Accept a natural-language question and return a structured response.

    Response type is one of: chart | table | comparison | text.
    The frontend renders each type dynamically via ResponseRenderer.
    """
    # TODO (Issue #11): parse_query → dispatch → respond
    return ChatResponse(
        response=TextResponse(
            message="Chat endpoint not yet implemented — coming in Issue #11.",
            is_error=False,
        )
    )
