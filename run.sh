#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# requires Python 3.10+ (this codebase uses `X | None` union syntax)
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r backend/requirements.txt

if [ ! -f backend/.env ]; then
  echo "backend/.env is missing. Copy backend/.env.example to backend/.env and set DEEPSEEK_API_KEY." >&2
  exit 1
fi

(cd frontend && npm install)

set -a
source backend/.env
set +a

.venv/bin/python -m uvicorn backend.main:app --port 8000 &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

# npm run dev spawns vite as its own child process (and may nest further,
# e.g. through an intermediate shell), rather than exec-ing into it, so
# killing FRONTEND_PID alone leaves descendants orphaned. Recurse down the
# whole tree instead of relying on `set -m` process-group semantics, which
# behave inconsistently across bash versions (notably macOS's stock bash 3.2).
kill_tree() {
  local pid="$1"
  local child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null
}

cleanup() {
  kill_tree "$FRONTEND_PID"
  kill "$BACKEND_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
