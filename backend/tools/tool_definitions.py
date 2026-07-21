"""4 tool JSON schemas for the LLM (name/description/params only).

Static schema definitions, no execution logic — execution lives in
conversation_service, calling repository methods.

Rule mentions in these descriptions ("only adjacent moves," "only the
assigned technician") are UX, not the security boundary. They exist so
the model tries to behave correctly and can frame its replies accurately
to the user — they are NOT trusted to self-enforce. The real gate is
rule_validator.py, applied to every proposed tool call before it reaches
work_order_repo.py.

Likewise, the "enum" on update_status's status field is a hint, not a
guarantee: models don't always respect enum constraints, so a malformed
or hallucinated status can still arrive here. rule_validator.py must
explicitly check status values itself — it cannot assume this schema
already filtered them out.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_work_order",
            "description": "Look up a work order by its ID. Read-only, no ownership restriction.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Work order ID, e.g. WO-001"}},
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_status",
            "description": "Change a work order's status. Only adjacent moves on Open ↔ In Progress ↔ On Hold ↔ Completed are valid — no skipping steps. Only the assigned technician may do this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "status": {"type": "string", "enum": ["Open", "In Progress", "On Hold", "Completed"]},
                },
                "required": ["id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Attach a note to a work order. Only the assigned technician may do this.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                "required": ["id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate",
            "description": "Flag a work order for a supervisor with a reason. Only the assigned technician may do this.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["id", "reason"],
            },
        },
    },
]
