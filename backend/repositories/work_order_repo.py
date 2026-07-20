"""In-memory read/write access to work-order state.

The only layer that touches work_orders.json / in-memory state directly.
Has no knowledge of ownership rules or status-flow legality — it just
executes what it's told. That logic lives one layer up, in
rule_validator.py. Keeping this repo "dumb" is what makes the guard
testable in isolation.
"""

import json
from datetime import datetime, timezone

from backend.models.schemas import CurrentUser, Note, WorkOrder, Status

_work_orders: dict[str, WorkOrder] = {}
_current_user: CurrentUser | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: str) -> None:
    global _current_user, _work_orders
    with open(path) as f:
        data = json.load(f)

    user = CurrentUser(**data["currentUser"])
    work_orders: dict[str, WorkOrder] = {}
    for raw in data["workOrders"]:
        wo = WorkOrder(
            **{
                "notes": [],
                "escalated": False,
                "escalationReason": None,
                **raw,
            }
        )
        work_orders[wo.id] = wo

    _current_user = user
    _work_orders = work_orders


def get(id: str) -> WorkOrder | None:
    return _work_orders.get(id)


def get_all() -> list[WorkOrder]:
    return list(_work_orders.values())


def update_status(id: str, new_status: Status) -> WorkOrder:
    wo = _work_orders[id]
    wo.status = new_status
    return wo


def add_note(id: str, text: str) -> WorkOrder:
    wo = _work_orders[id]
    wo.notes.append(Note(text=text, timestamp=_now_iso()))
    return wo


def set_escalated(id: str, reason: str) -> WorkOrder:
    wo = _work_orders[id]
    wo.escalated = True
    wo.escalationReason = reason
    add_note(id, f"Escalated: {reason}")
    return wo


def current_user() -> CurrentUser:
    if _current_user is None:
        raise RuntimeError("work_order_repo.load() has not been called")
    return _current_user
