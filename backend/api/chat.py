"""HTTP layer only: POST /chat, GET /work-orders. No logic."""

from fastapi import APIRouter

from backend.models.schemas import ChatRequest, ChatResponse
from backend.repositories import work_order_repo
from backend.services import conversation_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    return conversation_service.handle_turn(req.message)


@router.get("/work-orders")
def list_work_orders():
    return work_order_repo.get_all()
