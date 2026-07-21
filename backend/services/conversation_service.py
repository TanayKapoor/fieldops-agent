"""Orchestrates one turn: call LLM -> dispatch tool -> retry-on-malformed loop.

last_wo_id is a system-prompt hint only, not something that overrides the
model's tool-call args — pronoun resolution ("mark it done") stays with the
LLM via full conversation history; last_wo_id just nudges it in the prompt.

A single user turn can involve multiple tool calls in sequence (e.g. the
model looks up a work order before deciding how to update it) — each tool
call gets its own malformed-retry budget of 1, and the loop keeps going
until the model returns a plain-content reply or hits MAX_TOOL_STEPS.
"""

import json
import threading

from backend.llm.deepseek_client import call_model
from backend.models.schemas import ChatMessage, ChatResponse
from backend.repositories import work_order_repo as repo
from backend.services import knowledge_service
from backend.state import state
from backend.tools.tool_definitions import TOOLS
from backend.validators.rule_validator import ValidationResult, validate_tool_call

MALFORMED_RETRY_BUDGET = 1
MAX_TOOL_STEPS = 5  # ponytail: hard cap against a model looping tool calls forever

# FastAPI's sync def endpoints run in a threadpool, so concurrent /chat calls
# (two tabs, a double-click before the frontend's `loading` disables the
# button) can otherwise interleave reads/writes on the shared `state`
# singleton mid-turn. One lock per turn is enough for this single-user-scoped
# app: it doesn't add multi-session support, it just makes the existing
# single shared conversation atomic per turn instead of racy.
_turn_lock = threading.Lock()

# tool name -> repo function. escalate maps to set_escalated; repo's arg name
# for the id is positional so callers just need id + the tool's own args.
_TOOL_DISPATCH = {
    "get_work_order": lambda args: repo.get(args["id"]),
    "update_status": lambda args: repo.update_status(args["id"], args["status"]),
    "add_note": lambda args: repo.add_note(args["id"], args["text"]),
    "escalate": lambda args: repo.set_escalated(args["id"], args["reason"]),
}


def _grounding_instruction(user_message: str) -> str:
    section, _score = knowledge_service.search(user_message)
    if section is None:
        return (
            "NO_MATCH: no knowledge base section is relevant to this question. "
            "If the user is asking a factual question, you must say you don't "
            "know rather than guessing."
        )
    return (
        f"{section.body}\n\n"
        "Answer only using the context above; if it doesn't fully answer the "
        "question, say what you don't know."
    )


def _build_system_prompt(user_message: str) -> str:
    parts = [
        "You are a field operations assistant helping a technician manage work orders. "
        "Use the available tools to look up, update, annotate, or escalate work orders "
        "when the user asks you to. Do not fabricate work order IDs, statuses, or "
        "knowledge-base facts.",
        _grounding_instruction(user_message),
    ]
    if state.last_wo_id:
        parts.append(
            f"The work order most recently discussed is {state.last_wo_id}. "
            "If the user refers to it ambiguously (e.g. 'it', 'that one'), this is "
            "a hint, not a substitute for your own judgment from the conversation."
        )
    return "\n\n".join(parts)


def _messages_for_model(user_message: str) -> list[dict]:
    system_prompt = _build_system_prompt(user_message)
    history = [msg.model_dump(exclude={"tool_call_summary"}) for msg in state.history]
    return [{"role": "system", "content": system_prompt}, *history]


def _summarize_call(tool_name: str, args: dict) -> str:
    # id first (it's the subject), then remaining args in declared order,
    # positional-style: update_status(WO-002, In Progress)
    ordered = [args["id"]] + [v for k, v in args.items() if k != "id"]
    return f"{tool_name}({', '.join(str(v) for v in ordered)})"


def _assistant_tool_call_msg(assistant_message, tool_calls) -> dict:
    return {
        "role": "assistant",
        "content": assistant_message.content,
        "tool_calls": [tc.model_dump() for tc in tool_calls],
    }


def _all_tool_calls(message):
    tool_calls = getattr(message, "tool_calls", None)
    return list(tool_calls) if tool_calls else []


def handle_turn(user_message: str) -> ChatResponse:
    with _turn_lock:
        return _handle_turn_locked(user_message)


def _handle_turn_locked(user_message: str) -> ChatResponse:
    state.history.append(ChatMessage(role="user", content=user_message))

    messages = _messages_for_model(user_message)
    summaries: list[str] = []

    for _ in range(MAX_TOOL_STEPS):
        message = call_model(messages, TOOLS)
        tool_calls = _all_tool_calls(message)

        if not tool_calls:
            reply = message.content or ""
            state.history.append(ChatMessage(
                role="assistant",
                content=reply,
                tool_call_summary=summaries[-1] if summaries else None,
            ))
            return ChatResponse(reply=reply, tool_calls=summaries)

        outcome = _run_tool_calls(messages, message, tool_calls)

        if outcome.stop_reply is not None:
            # rule_violation or malformed-retry-exhausted: hard stop, no further steps
            summaries.extend(outcome.summaries)
            state.history.append(ChatMessage(
                role="assistant",
                content=outcome.stop_reply,
                tool_call_summary=outcome.summaries[-1] if outcome.summaries else None,
            ))
            return ChatResponse(reply=outcome.stop_reply, tool_calls=summaries)

        # ok: record the summaries, extend the running message list, loop again
        summaries.extend(outcome.summaries)
        messages = outcome.messages

    if summaries:
        # partial progress before hitting the step cap: say what happened
        # instead of an unconditional failure that erases completed work
        reply = "I made some progress but couldn't finish everything you asked in one go: " + "; ".join(summaries)
    else:
        reply = "I wasn't able to complete that request."
    state.history.append(ChatMessage(role="assistant", content=reply, tool_call_summary=summaries[-1] if summaries else None))
    return ChatResponse(reply=reply, tool_calls=summaries)


class _StepOutcome:
    def __init__(self, *, messages=None, summaries=None, stop_reply=None):
        self.messages = messages
        self.summaries = summaries or []
        self.stop_reply = stop_reply


def _validate_one(tool_call):
    tool_name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return tool_name, None, ValidationResult(ok=False, error_kind="malformed", reason="Arguments were not valid JSON.")
    return tool_name, args, validate_tool_call(tool_name, args, repo.current_user(), repo.get)


def _run_tool_calls(messages, assistant_message, tool_calls, retries_left=MALFORMED_RETRY_BUDGET):
    validated = [(tc, *_validate_one(tc)) for tc in tool_calls]

    # a rule violation anywhere in the batch hard-stops the whole turn —
    # never let it slip through bundled with other, valid calls
    for tool_call, tool_name, args, result in validated:
        if not result.ok and result.error_kind == "rule_violation":
            summary = f"✗ {tool_name}({args['id']}) — rejected: {result.reason}"
            return _StepOutcome(summaries=[summary], stop_reply=result.reason)

    malformed = [(tc, name, result) for tc, name, args, result in validated if not result.ok]
    if malformed:
        if retries_left <= 0:
            return _StepOutcome(stop_reply="I wasn't able to complete that request.")

        # retry the whole batch: give the model every tool's error back at once
        tool_result_msgs = [
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": f"Success: {name} completed." if result.ok else f"Error: {result.reason}",
            }
            for tc, name, args, result in validated
        ]
        retry_messages = [*messages, _assistant_tool_call_msg(assistant_message, tool_calls), *tool_result_msgs]
        retry_message = call_model(retry_messages, TOOLS)

        retry_calls = _all_tool_calls(retry_message)
        if not retry_calls:
            reply = retry_message.content or ""
            return _StepOutcome(stop_reply=reply)

        return _run_tool_calls(retry_messages, retry_message, retry_calls, retries_left - 1)

    # every call in the batch validated ok: execute them all
    tool_result_msgs = []
    summaries = []
    for tool_call, tool_name, args, result in validated:
        wo = _TOOL_DISPATCH[tool_name](args)
        state.last_wo_id = wo.id if wo is not None else args.get("id")

        content = f"Success: {tool_name} completed. {wo.model_dump_json()}" if wo is not None else f"Success: {tool_name} completed."
        tool_result_msgs.append({"role": "tool", "tool_call_id": tool_call.id, "content": content})
        summaries.append(f"→ {_summarize_call(tool_name, args)}")

    new_messages = [*messages, _assistant_tool_call_msg(assistant_message, tool_calls), *tool_result_msgs]
    return _StepOutcome(messages=new_messages, summaries=summaries)
