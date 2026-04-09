"""面试核心 API 路由。"""

import json
import uuid
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from sse_starlette.sse import EventSourceResponse

from config.settings import settings
from backend.session_store import store
from backend.schemas import (
    SelectJobRequest,
    SelectJobResponse,
    SubmitAnswerRequest,
    StartInterviewResponse,
    InterviewStatusResponse,
    RunCodeRequest,
    RunCodeResponse,
    ReportResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["interview"])


@router.post("/interview", response_model=StartInterviewResponse)
async def start_interview(file: UploadFile = File(...)):
    """上传简历 PDF 并创建面试会话。"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "请上传 PDF 格式的简历文件")

    session_id = str(uuid.uuid4())[:8]
    iface = store.create(session_id)

    settings.ensure_dirs()
    save_path = Path(settings.upload_dir) / f"{session_id}_{file.filename}"
    content = await file.read()
    save_path.write_bytes(content)

    try:
        text, _audio = await asyncio.to_thread(
            iface.start_interview, str(save_path), session_id
        )
    except Exception as e:
        store.remove(session_id)
        logger.exception("简历解析失败")
        raise HTTPException(500, f"简历解析失败: {e}")

    return StartInterviewResponse(session_id=session_id, greeting=text)


@router.post("/interview/{session_id}/select-job", response_model=SelectJobResponse)
async def select_job(session_id: str, body: SelectJobRequest):
    """选择目标岗位并生成面试题。"""
    iface = store.get(session_id)
    if iface is None:
        raise HTTPException(404, "会话不存在")

    try:
        text, _audio = await asyncio.to_thread(
            iface.select_job, body.job_category, body.include_coding
        )
    except Exception as e:
        logger.exception("生成面试题失败")
        raise HTTPException(500, f"生成面试题失败: {e}")

    agent_state = store.get_state(session_id)
    questions_count = len(agent_state.get("questions", []))

    return SelectJobResponse(message=text, questions_count=questions_count)


@router.post("/interview/{session_id}/answer")
async def submit_answer(session_id: str, body: SubmitAnswerRequest):
    """提交回答并以 SSE 流式返回面试官响应。"""
    iface = store.get(session_id)
    if iface is None:
        raise HTTPException(404, "会话不存在")

    async def event_generator():
        yield {"event": "status", "data": json.dumps({"status": "processing"})}

        try:
            response, audio_out = await asyncio.to_thread(
                iface.process_text_input, body.answer
            )

            agent_state = store.get_state(session_id)
            current_idx = agent_state.get("current_question_idx", 0)
            questions = agent_state.get("questions", [])
            current_q = questions[current_idx] if current_idx < len(questions) else None

            yield {
                "event": "response",
                "data": json.dumps({
                    "text": response,
                    "is_finished": iface.is_finished,
                    "phase": agent_state.get("interview_phase", ""),
                    "current_question": current_q,
                    "audio_available": bool(audio_out),
                }, ensure_ascii=False),
            }
        except Exception as e:
            logger.exception("处理回答失败")
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}, ensure_ascii=False),
            }

        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())


@router.get("/interview/{session_id}/status", response_model=InterviewStatusResponse)
async def get_status(session_id: str):
    """获取面试当前状态。"""
    iface = store.get(session_id)
    if iface is None:
        raise HTTPException(404, "会话不存在")

    progress = iface.get_current_progress()
    agent_state = store.get_state(session_id)

    current_idx = agent_state.get("current_question_idx", 0)
    questions = agent_state.get("questions", [])
    current_q = questions[current_idx] if current_idx < len(questions) else None

    return InterviewStatusResponse(
        phase=agent_state.get("interview_phase", "init"),
        progress=progress,
        is_finished=iface.is_finished,
        current_question=current_q,
    )


@router.get("/interview/{session_id}/report", response_model=ReportResponse)
async def get_report(session_id: str):
    """获取面试反馈报告。"""
    iface = store.get(session_id)
    if iface is None:
        raise HTTPException(404, "会话不存在")

    if not iface.is_finished:
        raise HTTPException(400, "面试尚未结束")

    report = iface.get_report()
    history = iface.get_conversation_history()
    return ReportResponse(report=report, conversation_history=history)


@router.post("/interview/{session_id}/code/run", response_model=RunCodeResponse)
async def run_code(session_id: str, body: RunCodeRequest):
    """运行代码样例测试。"""
    iface = store.get(session_id)
    if iface is None:
        raise HTTPException(404, "会话不存在")

    from core.code_runner import verify_solution
    from core.leetcode_manager import get_problem_by_id

    problem = get_problem_by_id(body.leetcode_id)
    if not problem:
        raise HTTPException(404, f"未找到 LeetCode #{body.leetcode_id}")

    if body.language != "python3":
        return RunCodeResponse(
            success=False, passed=0, total=0,
            output="", error=f"本地运行仅支持 Python3，{body.language} 请到 LeetCode 提交验证",
        )

    result = await asyncio.to_thread(verify_solution, body.code, problem)
    return RunCodeResponse(**result)


@router.get("/interview/config/job-categories")
async def get_job_categories():
    """获取可选岗位列表。"""
    return {"categories": settings.job_categories}


@router.get("/interview/config/providers")
async def get_providers():
    """获取可用 LLM Provider 列表。"""
    from core.llm.providers import PROVIDERS
    return {
        "providers": [
            {
                "id": k,
                "name": v.name,
                "models": v.models,
                "default_model": v.default_model,
            }
            for k, v in PROVIDERS.items()
        ],
        "current": settings.llm_provider,
    }
