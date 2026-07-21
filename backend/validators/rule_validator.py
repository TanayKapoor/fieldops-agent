"""Ownership + status-flow adjacency + arg/schema checks — the real gate.

Pure functions, no side effects: given a proposed tool call + current
state, return allow/deny + reason.

error_kind distinguishes two categories conversation_service.py branches on:
- "malformed": the call itself is broken (bad tool name, bad/missing args,
  a work order ID or status string that doesn't exist) — worth a retry,
  since the model may have hallucinated or mistyped something it can correct.
- "rule_violation": the call is well-formed but crosses a real boundary
  (wrong owner, illegal status jump) — a hard refusal, no retry, since
  retrying the same request won't make it more allowed.

Ordering note: ownership is checked before status-flow adjacency. If a tech
targets someone else's work order with both a wrong owner AND an illegal
status jump, the response must say "not your work order" — it must not leak
status-flow details about a work order the caller doesn't own.
"""

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from backend.models.schemas import CurrentUser, WorkOrder

STATUS_ORDER = ["Open", "In Progress", "On Hold", "Completed"]

# tools where the caller must own the work order to act on it
_OWNERSHIP_REQUIRED = {"update_status", "add_note", "escalate"}

_REQUIRED_ARGS: dict[str, dict[str, type]] = {
    "get_work_order": {"id": str},
    "update_status": {"id": str, "status": str},
    "add_note": {"id": str, "text": str},
    "escalate": {"id": str, "reason": str},
}


@dataclass
class ValidationResult:
    ok: bool
    error_kind: Optional[Literal["malformed", "rule_violation"]] = None
    reason: Optional[str] = None


def _malformed(reason: str) -> ValidationResult:
    return ValidationResult(ok=False, error_kind="malformed", reason=reason)


def _rule_violation(reason: str) -> ValidationResult:
    return ValidationResult(ok=False, error_kind="rule_violation", reason=reason)


def validate_tool_call(
    tool_name: str,
    args: dict,
    current_user: CurrentUser,
    get_work_order_fn: Callable[[str], Optional[WorkOrder]],
) -> ValidationResult:
    if tool_name not in _REQUIRED_ARGS:
        return _malformed(f"Unknown tool: {tool_name!r}")

    for arg_name, arg_type in _REQUIRED_ARGS[tool_name].items():
        if arg_name not in args:
            return _malformed(f"{tool_name}: missing required arg {arg_name!r}")
        if not isinstance(args[arg_name], arg_type):
            return _malformed(f"{tool_name}: arg {arg_name!r} must be a string")

    work_order = get_work_order_fn(args["id"])
    if work_order is None:
        return _malformed(f"No such work order: {args['id']!r}")

    if tool_name in _OWNERSHIP_REQUIRED and work_order.assignedTech != current_user.id:
        return _rule_violation("This work order is not assigned to you.")

    if tool_name == "update_status":
        new_status = args["status"]
        if new_status not in STATUS_ORDER:
            return _malformed(f"Not a valid status: {new_status!r}")

        current_index = STATUS_ORDER.index(work_order.status)
        new_index = STATUS_ORDER.index(new_status)
        if abs(new_index - current_index) != 1:
            return _rule_violation(
                f"Cannot move status from {work_order.status!r} to {new_status!r} — "
                "only adjacent status changes are allowed."
            )

    return ValidationResult(ok=True)
