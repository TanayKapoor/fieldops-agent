"""Smoke test for work_order_repo. Run: python -m backend.repositories.test_work_order_repo"""

from backend.repositories import work_order_repo as repo


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"failed: {label}")


def main():
    repo.load("backend/work_orders.json")

    check("current_user().name", repo.current_user().name == "Alex Rivera")
    all_wos = repo.get_all()
    check("get_all() length", len(all_wos) == 2)

    wo = repo.get("WO-001")
    check("get() found", wo is not None)
    check("notes starts empty", wo.notes == [])
    check("escalated starts False", wo.escalated is False)

    repo.update_status("WO-001", "In Progress")
    check("update_status applied", repo.get("WO-001").status == "In Progress")

    repo.add_note("WO-001", "Started work")
    check("add_note appended", len(repo.get("WO-001").notes) == 1)

    repo.set_escalated("WO-001", "Missing part")
    wo = repo.get("WO-001")
    check("escalated set True", wo.escalated is True)
    check("escalationReason set", wo.escalationReason == "Missing part")
    check("set_escalated calls add_note internally", len(wo.notes) == 2)

    check("get() missing id returns None", repo.get("WO-999") is None)

    print("ok")


if __name__ == "__main__":
    main()
