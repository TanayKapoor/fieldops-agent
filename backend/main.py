"""App entrypoint. Mounts routers — nothing else."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.chat import router
from backend.repositories import work_order_repo

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default dev port
    allow_methods=["*"],
    allow_headers=["*"],
)

work_order_repo.load(str(Path(__file__).resolve().parent / "work_orders.json"))
app.include_router(router)
