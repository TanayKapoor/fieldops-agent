"""Smoke test for the HTTP layer, using FastAPI's TestClient (no live server).

/chat calls the real conversation_service, which calls the real DeepSeek API,
so DEEPSEEK_API_KEY must be set to run this.

Run: DEEPSEEK_API_KEY=... python -m backend.api.test_chat
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"failed: {label}")


def main():
    response = client.get("/work-orders")
    check("GET /work-orders status 200", response.status_code == 200)
    work_orders = response.json()
    check("GET /work-orders returns a list", isinstance(work_orders, list))
    check("GET /work-orders non-empty", len(work_orders) > 0)
    check("each work order has an id", all("id" in wo for wo in work_orders))

    response = client.post("/chat", json={"message": "How do I reset a CU unit?"})
    check("POST /chat status 200", response.status_code == 200)
    body = response.json()
    check("POST /chat response has reply", isinstance(body.get("reply"), str) and body["reply"])
    check("POST /chat response has tool_calls list", isinstance(body.get("tool_calls"), list))

    print("ok")


if __name__ == "__main__":
    main()
