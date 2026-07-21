"""Shape check for TOOLS. Run: python -m backend.tools.test_tool_definitions"""

from backend.tools.tool_definitions import TOOLS


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"failed: {label}")


STATUS_ENUM = ["Open", "In Progress", "On Hold", "Completed"]

EXPECTED_PROPERTIES = {
    "get_work_order": {"id": {"type": "string", "description": "Work order ID, e.g. WO-001"}},
    "update_status": {
        "id": {"type": "string"},
        "status": {"type": "string", "enum": STATUS_ENUM},
    },
    "add_note": {"id": {"type": "string"}, "text": {"type": "string"}},
    "escalate": {"id": {"type": "string"}, "reason": {"type": "string"}},
}

EXPECTED_REQUIRED = {
    "get_work_order": ["id"],
    "update_status": ["id", "status"],
    "add_note": ["id", "text"],
    "escalate": ["id", "reason"],
}


def main():
    check("4 tools defined", len(TOOLS) == 4)

    expected_names = {"get_work_order", "update_status", "add_note", "escalate"}
    names = set()
    for tool in TOOLS:
        check("type is function", tool.get("type") == "function")
        fn = tool.get("function", {})
        check("has name", isinstance(fn.get("name"), str) and fn["name"])
        check("has description", isinstance(fn.get("description"), str) and fn["description"])
        params = fn.get("parameters")
        check("has parameters object", isinstance(params, dict) and params.get("type") == "object")
        check("has properties", isinstance(params.get("properties"), dict))
        check("has required list", isinstance(params.get("required"), list))
        for req in params["required"]:
            check(f"{fn['name']}: required field '{req}' is declared", req in params["properties"])

        name = fn["name"]
        check(f"{name}: known tool name", name in EXPECTED_PROPERTIES)
        check(
            f"{name}: properties match expected schema exactly",
            params["properties"] == EXPECTED_PROPERTIES[name],
        )
        check(
            f"{name}: required fields match expected list exactly",
            params["required"] == EXPECTED_REQUIRED[name],
        )

        names.add(name)

    check("names match expected set", names == expected_names)

    print("ok")


if __name__ == "__main__":
    main()
