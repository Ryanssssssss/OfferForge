"""历史会话 API 路由。"""

from fastapi import APIRouter, HTTPException

from core.session_manager import list_sessions, delete_session, load_session
from backend.schemas import SessionItem

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionItem])
async def get_sessions():
    """获取历史会话列表。"""
    raw = list_sessions()
    return [
        SessionItem(
            session_id=s["session_id"],
            candidate_name=s.get("candidate_name", ""),
            job_category=s.get("job_category", ""),
            saved_at=s.get("saved_at"),
            has_report=s.get("has_report", False),
        )
        for s in raw
    ]


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取单个历史会话详情。"""
    data = load_session(session_id)
    if not data:
        raise HTTPException(404, "会话不存在")
    return data


@router.delete("/{session_id}")
async def remove_session(session_id: str):
    """删除历史会话。"""
    delete_session(session_id)
    return {"ok": True}
