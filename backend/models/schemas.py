"""Pydantic models: WorkOrder, Note, ChatMessage, ChatRequest/Response.

Shared types everything else imports.
"""

from pydantic import BaseModel
from typing import Literal, Optional

Status = Literal["Open", "In Progress", "On Hold", "Completed"]


class Note(BaseModel):
    text: str
    timestamp: str  # ISO 8601


class WorkOrder(BaseModel):
    id: str
    title: str
    assetType: str
    assignedTech: str
    status: Status
    dueDate: str
    steps: list[str]
    notes: list[Note] = []
    escalated: bool = False
    escalationReason: Optional[str] = None


class CurrentUser(BaseModel):
    id: str
    name: str
    role: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    tool_call_summary: Optional[str] = None  # for the muted UI line


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[str] = []  # human-readable summaries, e.g. "escalate(WO-006, ...)"
