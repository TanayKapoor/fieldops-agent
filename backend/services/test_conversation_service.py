"""Integration script for conversation_service. Hits the real DeepSeek API.

Not a unit test — handle_turn() calls a live model, so this is a scripted
set of conversations to run and eyeball, not something to assert on in CI.

Run: DEEPSEEK_API_KEY=... python -m backend.services.test_conversation_service
(requires backend/work_orders.json to be loaded first, done below)
"""

from backend.repositories import work_order_repo as repo
from backend.services.conversation_service import _TOOL_DISPATCH, handle_turn
from backend.state import state
from backend.validators.rule_validator import _REQUIRED_ARGS


def test_tool_dispatch_matches_validator_registry():
    """_TOOL_DISPATCH (conversation_service) and _REQUIRED_ARGS (rule_validator)
    are maintained separately; if they drift, a tool could be dispatchable but
    unvalidated; or validated but silently undispatchable."""
    assert set(_TOOL_DISPATCH) == set(_REQUIRED_ARGS), (
        f"tool name mismatch: dispatch={set(_TOOL_DISPATCH)} validator={set(_REQUIRED_ARGS)}"
    )


def reset_state():
    repo.load("backend/work_orders.json")
    state.history.clear()
    state.last_wo_id = None


def run(label: str, user_message: str):
    print(f"\n--- {label} ---")
    print(f"user: {user_message}")
    response = handle_turn(user_message)
    print(f"reply: {response.reply}")
    print(f"tool_calls: {response.tool_calls}")
    return response


def main():
    repo.load("backend/work_orders.json")

    # 1. Plain KB question -> grounded answer
    reset_state()
    run("KB question, grounded", "How do I reset a CU unit?")

    # 2. Plain KB question -> no match, model should say it doesn't know
    reset_state()
    run("KB question, no match", "What's the weather like today?")

    # 3. Successful tool call: status update on own WO
    # tech-ravi owns WO-002 (currently "Open"); Open -> In Progress is adjacent
    reset_state()
    run("Successful status update", "Mark WO-002 as In Progress.")

    # 4. Ownership rejection: WO-004 is assigned to tech-priya, not tech-ravi
    reset_state()
    run("Ownership rejection", "Add a note to WO-004 saying 'checked in'.")

    # 5. Illegal status jump: WO-002 is "Open", Open -> Completed skips steps
    reset_state()
    run("Illegal status jump", "Set WO-002 straight to Completed.")

    # 6. Malformed retry-and-recover: prompt a bogus status, expect the model
    # to self-correct to a valid one on the tool-error retry. WO-002 starts
    # "Open", so "In Progress" is the only valid next status to name here.
    reset_state()
    run(
        "Malformed status retry-and-recover",
        "Update WO-002's status to 'Fixed'. If that's not a valid status, "
        "use 'In Progress' instead.",
    )


if __name__ == "__main__":
    main()
