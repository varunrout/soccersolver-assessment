"""
routers/chat.py — POST /chat

Three-layer architecture (implemented in Issues #9, #10, #11):
    Layer 1  nlu/parser.py          parse_query(text) → ParsedIntent
    Layer 2  services/chat_service  execute_chat_query() → ChatResponse
    Layer 3  routers/chat.py        receive → dispatch → respond

This router contains ZERO business logic.
"""

from fastapi import APIRouter

from models.chat_responses import ChatRequest, ChatResponse
from services.chat_service import execute_chat_query

router = APIRouter()


@router.post("", response_model=ChatResponse, summary="Conversational analytics query")
def chat(request: ChatRequest) -> ChatResponse:
    """
    Accept a natural-language question and return a structured response.

    Response type is one of: chart | table | comparison | text.
    The frontend renders each type dynamically via ResponseRenderer.
    """
    return execute_chat_query(request.message)
