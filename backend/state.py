"""Global in-memory session singleton (history, last_wo_id).

Work-order state itself lives in work_order_repo.py's internal store,
not duplicated here — this only holds conversational memory.
"""

from backend.models.schemas import ChatMessage


class AppState:
    def __init__(self):
        self.history: list[ChatMessage] = []
        self.last_wo_id: str | None = None


state = AppState()
