# fieldops-agent

A chat assistant for a field-service technician: look up, update, annotate, and escalate work orders, and answer procedural questions grounded strictly in a fixed knowledge base. The assistant never improvises an answer the knowledge base doesn't contain, and every write action (status change, note, escalation) is checked against ownership and status-flow rules in code before it executes — the LLM can only *propose* a tool call, never run one directly.

Backend: FastAPI + DeepSeek (OpenAI-compatible SDK). Frontend: Vite + React + TypeScript. State: in-memory, single technician, no persistence across restarts.

## Requirements

- Python 3.10+ (the backend uses `X | None` union syntax — on macOS, the stock `python3` may be older; install a newer one via `brew install python@3.12` if `run.sh` fails with a syntax error)
- Node.js + npm (for the Vite frontend)
- A DeepSeek API key

## Quickest start

```bash
cp backend/.env.example backend/.env
# edit backend/.env and set DEEPSEEK_API_KEY=sk-...

./run.sh
```

`run.sh` handles everything else: creates `.venv` if missing, installs backend deps from `backend/requirements.txt`, installs frontend deps (`npm install`), then starts both servers together:

- backend on `http://localhost:8000`
- frontend on `http://localhost:5173`

Open `http://localhost:5173` in a browser. Press `Ctrl+C` to stop both servers — the script tears down the whole process tree (including Vite's child processes), not just the top-level ones.

## Manual start (if you want each piece separately)

**1. Backend**

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

cp backend/.env.example backend/.env
# edit backend/.env and set DEEPSEEK_API_KEY=sk-...

set -a && source backend/.env && set +a
.venv/bin/python -m uvicorn backend.main:app --port 8000
```

The backend loads `backend/work_orders.json` once at startup — this is the seed data (work orders + current user). Changes made during a session (status updates, notes, escalations) are in-memory only and are lost on restart.

**2. Frontend**

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite serves on `http://localhost:5173` by default; the frontend's API base URL is hardcoded to `http://localhost:8000` in `frontend/src/App.tsx`. CORS for that origin is already configured in `backend/main.py`.

## Verifying it's working

```bash
curl http://localhost:8000/work-orders
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message": "How do I reset a CU unit?"}'
```

Both should return JSON. The second should return a grounded answer citing the reset procedure from `backend/knowledge.md`.

## Running the test suite

Each backend layer has its own runnable check (no pytest required, plain `python -m`):

```bash
set -a && source backend/.env && set +a   # DEEPSEEK_API_KEY must be set — some tests hit the real API

.venv/bin/python -m backend.repositories.test_work_order_repo
.venv/bin/python -m backend.services.test_knowledge_service
.venv/bin/python -m backend.validators.test_rule_validator
.venv/bin/python -m backend.tools.test_tool_definitions
.venv/bin/python -m backend.api.test_chat
```

`backend/services/test_conversation_service.py` is a scripted integration run against the live model (not an automated assertion suite) — run it the same way and read the output:

```bash
.venv/bin/python -m backend.services.test_conversation_service
```

Frontend has no automated tests; verify with `cd frontend && npx tsc -b && npm run build`.

## Project layout

```
backend/
├── main.py                # FastAPI app entrypoint: CORS, load work_orders.json, mount router
├── api/chat.py             # HTTP layer: POST /chat, GET /work-orders
├── services/
│   ├── conversation_service.py  # orchestrates one turn: LLM -> validator -> repo loop
│   └── knowledge_service.py     # parses knowledge.md, scores queries for grounding
├── validators/rule_validator.py # ownership + status-flow + malformed-call checks (the real gate)
├── llm/deepseek_client.py  # thin DeepSeek API wrapper
├── repositories/work_order_repo.py  # only module that touches work_orders.json
├── models/schemas.py       # shared Pydantic types
├── tools/tool_definitions.py  # tool JSON schemas given to the LLM
├── state.py                # in-memory chat history + last-referenced work order id
├── knowledge.md             # the knowledge base the assistant is grounded in
└── work_orders.json          # seed data: current user + work orders

frontend/
└── src/App.tsx              # single-component chat UI

run.sh          # starts both servers, one command
DECISIONS.md    # answers to the assignment's three required design questions
```

See `DECISIONS.md` for the reasoning behind the grounding threshold, the prompt-vs-code enforcement split, and the malformed-vs-rule_violation retry logic.
