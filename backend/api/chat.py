"""HTTP layer only: POST /chat, GET /work-orders. No logic."""

from fastapi import APIRouter

from backend.llm.deepseek_client import LLMUnavailableError
from backend.models.schemas import ChatRequest, ChatResponse
from backend.repositories import work_order_repo
from backend.services import conversation_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        return conversation_service.handle_turn(req.message)
    except LLMUnavailableError:
        return ChatResponse(reply="The assistant is temporarily unavailable. Please try again.", tool_calls=[])


@router.get("/work-orders")
def list_work_orders():
    return work_order_repo.get_all()


@router.get("/me")
def me():
    return work_order_repo.current_user()
