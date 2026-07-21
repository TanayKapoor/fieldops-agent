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

from backend.llm.deepseek_client import call_model
from backend.models.schemas import ChatMessage, ChatResponse
from backend.repositories import work_order_repo as repo
from backend.services import knowledge_service
from backend.state import state
from backend.tools.tool_definitions import TOOLS
from backend.validators.rule_validator import ValidationResult, validate_tool_call

MALFORMED_RETRY_BUDGET = 1
MAX_TOOL_STEPS = 5  # ponytail: hard cap against a model looping tool calls forever

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
    return [{"role": "system", "content": system_prompt}] + history


def _summarize_call(tool_name: str, args: dict) -> str:
    # id first (it's the subject), then remaining args in declared order,
    # positional-style: update_status(WO-002, In Progress)
    ordered = [args["id"]] + [v for k, v in args.items() if k != "id"]
    return f"{tool_name}({', '.join(str(v) for v in ordered)})"


def _assistant_tool_call_msg(assistant_message, tool_call) -> dict:
    return {
        "role": "assistant",
        "content": assistant_message.content,
        "tool_calls": [tool_call.model_dump()],
    }


def _first_tool_call(message):
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        return None
    return tool_calls[0]


def handle_turn(user_message: str) -> ChatResponse:
    state.history.append(ChatMessage(role="user", content=user_message))

    messages = _messages_for_model(user_message)
    summaries: list[str] = []

    for _ in range(MAX_TOOL_STEPS):
        message = call_model(messages, TOOLS)
        tool_call = _first_tool_call(message)

        if tool_call is None:
            reply = message.content or ""
            state.history.append(ChatMessage(
                role="assistant",
                content=reply,
                tool_call_summary=summaries[-1] if summaries else None,
            ))
            return ChatResponse(reply=reply, tool_calls=summaries)

        outcome = _run_one_tool_call(messages, message, tool_call)

        if outcome.stop_reply is not None:
            # rule_violation or malformed-retry-exhausted: hard stop, no further steps
            if outcome.summary:
                summaries.append(outcome.summary)
            state.history.append(ChatMessage(
                role="assistant",
                content=outcome.stop_reply,
                tool_call_summary=outcome.summary,
            ))
            return ChatResponse(reply=outcome.stop_reply, tool_calls=summaries)

        # ok: record the summary, extend the running message list, loop again
        summaries.append(outcome.summary)
        messages = outcome.messages

    reply = "I wasn't able to complete that request."
    state.history.append(ChatMessage(role="assistant", content=reply))
    return ChatResponse(reply=reply, tool_calls=summaries)


class _StepOutcome:
    def __init__(self, *, messages=None, summary=None, stop_reply=None):
        self.messages = messages
        self.summary = summary
        self.stop_reply = stop_reply


def _run_one_tool_call(messages, assistant_message, tool_call, retries_left=MALFORMED_RETRY_BUDGET):
    tool_name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        result = ValidationResult(ok=False, error_kind="malformed", reason="Arguments were not valid JSON.")
    else:
        result = validate_tool_call(tool_name, args, repo.current_user(), repo.get)

    if result.ok:
        wo = _TOOL_DISPATCH[tool_name](args)
        state.last_wo_id = wo.id if wo is not None else args.get("id")

        content = f"Success: {tool_name} completed. {wo.model_dump_json()}" if wo is not None else f"Success: {tool_name} completed."
        tool_result_msg = {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": content,
        }
        new_messages = messages + [_assistant_tool_call_msg(assistant_message, tool_call), tool_result_msg]
        summary = f"→ {_summarize_call(tool_name, args)}"
        return _StepOutcome(messages=new_messages, summary=summary)

    if result.error_kind == "rule_violation":
        summary = f"✗ {tool_name}({args['id']}) — rejected: {result.reason}"
        return _StepOutcome(summary=summary, stop_reply=result.reason)

    # malformed
    if retries_left <= 0:
        return _StepOutcome(stop_reply="I wasn't able to complete that request.")

    tool_result_msg = {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": f"Error: {result.reason}",
    }
    retry_messages = messages + [_assistant_tool_call_msg(assistant_message, tool_call), tool_result_msg]
    retry_message = call_model(retry_messages, TOOLS)

    retry_call = _first_tool_call(retry_message)
    if retry_call is None:
        reply = retry_message.content or ""
        return _StepOutcome(stop_reply=reply)

    return _run_one_tool_call(retry_messages, retry_message, retry_call, retries_left - 1)
