"""FastAPI 入口 — SmartInterview 后端。"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中，以便 core/ config/ interfaces/ 的 import 正常工作
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.session_manager import cleanup_expired
from backend.api.interview import router as interview_router
from backend.api.voice import router as voice_router
from backend.api.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_expired()
    yield


app = FastAPI(title="SmartInterview API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview_router, prefix="/api")
app.include_router(voice_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
