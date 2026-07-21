"""Smoke test for rule_validator. Run: python -m backend.validators.test_rule_validator"""

from backend.models.schemas import CurrentUser, WorkOrder
from backend.validators.rule_validator import validate_tool_call

RAVI = CurrentUser(id="tech-ravi", name="Ravi Kumar", role="technician")

_WORK_ORDERS = {
    "WO-001": WorkOrder(
        id="WO-001", title="t", assetType="CU-4400", assignedTech="tech-ravi",
        status="Open", dueDate="2026-07-18", steps=[],
    ),
    "WO-004": WorkOrder(
        id="WO-004", title="t", assetType="CU-3300", assignedTech="tech-priya",
        status="In Progress", dueDate="2026-07-19", steps=[],
    ),
    "WO-003": WorkOrder(
        id="WO-003", title="t", assetType="CU-4400", assignedTech="tech-ravi",
        status="On Hold", dueDate="2026-07-16", steps=[],
    ),
}


def get_work_order(wo_id: str):
    return _WORK_ORDERS.get(wo_id)


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"failed: {label}")


def main():
    r = validate_tool_call("frobnicate", {"id": "WO-001"}, RAVI, get_work_order)
    check("unknown tool -> malformed", not r.ok and r.error_kind == "malformed")

    r = validate_tool_call("update_status", {"id": "WO-001"}, RAVI, get_work_order)
    check("missing status arg -> malformed", not r.ok and r.error_kind == "malformed")

    r = validate_tool_call("get_work_order", {"id": "WO-999"}, RAVI, get_work_order)
    check("nonexistent WO id -> malformed", not r.ok and r.error_kind == "malformed")

    r = validate_tool_call("add_note", {"id": "WO-004", "text": "hi"}, RAVI, get_work_order)
    check("add_note on someone else's WO -> rule_violation", not r.ok and r.error_kind == "rule_violation")

    r = validate_tool_call("escalate", {"id": "WO-004", "reason": "help"}, RAVI, get_work_order)
    check("escalate on someone else's WO -> rule_violation", not r.ok and r.error_kind == "rule_violation")

    r = validate_tool_call("update_status", {"id": "WO-001", "status": "Completed"}, RAVI, get_work_order)
    check("illegal jump Open->Completed on own WO -> rule_violation", not r.ok and r.error_kind == "rule_violation")

    r = validate_tool_call("update_status", {"id": "WO-001", "status": "In Progress"}, RAVI, get_work_order)
    check("legal jump Open->In Progress -> ok", r.ok)

    r = validate_tool_call("update_status", {"id": "WO-003", "status": "In Progress"}, RAVI, get_work_order)
    check("legal jump On Hold->In Progress -> ok", r.ok)

    r = validate_tool_call("get_work_order", {"id": "WO-004"}, RAVI, get_work_order)
    check("get_work_order on someone else's WO -> ok (read unrestricted)", r.ok)

    r = validate_tool_call("update_status", {"id": "WO-001", "status": "Fixed"}, RAVI, get_work_order)
    check("garbage status string -> malformed, not rule_violation", not r.ok and r.error_kind == "malformed")

    # ordering: wrong owner AND illegal jump at once -> must report ownership, not status-flow
    r = validate_tool_call("update_status", {"id": "WO-004", "status": "Completed"}, RAVI, get_work_order)
    check(
        "ownership checked before status-flow adjacency",
        not r.ok and r.error_kind == "rule_violation" and "not assigned" in r.reason,
    )

    # missing/wrong-typed arg: id not a string
    r = validate_tool_call("get_work_order", {"id": 123}, RAVI, get_work_order)
    check("wrong-typed id -> malformed", not r.ok and r.error_kind == "malformed")

    # malformed envelope: unhashable tool_name, args not a dict
    r = validate_tool_call(["get_work_order"], {"id": "WO-001"}, RAVI, get_work_order)
    check("unhashable tool_name -> malformed", not r.ok and r.error_kind == "malformed")

    r = validate_tool_call("get_work_order", ["WO-001"], RAVI, get_work_order)
    check("args not a dict -> malformed", not r.ok and r.error_kind == "malformed")

    r = validate_tool_call("get_work_order", None, RAVI, get_work_order)
    check("args is None -> malformed", not r.ok and r.error_kind == "malformed")

    print("ok")


def test_rule_validator():
    main()


if __name__ == "__main__":
    main()
