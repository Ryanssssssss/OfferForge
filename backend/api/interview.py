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


@router.get("/interview/resumes")
async def list_resumes():
    """列出已上传的简历文件。"""
    settings.ensure_dirs()
    upload_dir = Path(settings.upload_dir)
    resumes = []
    seen_names: set[str] = set()
    for f in sorted(upload_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
        original_name = "_".join(f.name.split("_")[1:]) or f.name
        if original_name in seen_names:
            continue
        seen_names.add(original_name)
        resumes.append({
            "path": str(f),
            "name": original_name,
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
        })
    return {"resumes": resumes}


@router.post("/interview")
async def start_interview(file: UploadFile = File(...)):
    """上传新简历 PDF，秒回 session_id。"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "请上传 PDF 格式的简历文件")

    session_id = str(uuid.uuid4())[:8]
    store.create(session_id)

    settings.ensure_dirs()
    save_path = Path(settings.upload_dir) / f"{session_id}_{file.filename}"
    content = await file.read()
    save_path.write_bytes(content)

    store.set_meta(session_id, "resume_path", str(save_path))

    return {"session_id": session_id}


@router.post("/interview/reuse")
async def reuse_resume(body: dict):
    """用已有简历创建新会话。"""
    resume_path = body.get("resume_path", "")
    if not resume_path or not Path(resume_path).exists():
        raise HTTPException(400, "简历文件不存在，请重新上传")

    session_id = str(uuid.uuid4())[:8]
    store.create(session_id)
    store.set_meta(session_id, "resume_path", resume_path)

    return {"session_id": session_id}


@router.post("/interview/{session_id}/parse")
async def parse_resume(session_id: str):
    """解析简历（耗时操作，由面试页调用，SSE 推送进度）。"""
    iface = store.get(session_id)
    if iface is None:
        raise HTTPException(404, "会话不存在")

    resume_path = store.get_meta(session_id, "resume_path")
    if not resume_path:
        raise HTTPException(400, "未找到简历文件，请重新上传")

    async def event_generator():
        yield {"event": "status", "data": json.dumps({"status": "parsing"})}
        try:
            text, _audio = await asyncio.to_thread(
                iface.start_interview, resume_path, session_id
            )
            yield {
                "event": "done",
                "data": json.dumps({"greeting": text}, ensure_ascii=False),
            }
        except Exception as e:
            logger.exception("简历解析失败")
            store.remove(session_id)
            yield {
                "event": "error",
                "data": json.dumps({"message": f"简历解析失败: {e}"}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/interview/{session_id}/select-job")
async def select_job(session_id: str, body: SelectJobRequest):
    """选择目标岗位并生成面试题（SSE 流式，避免代理超时）。"""
    iface = store.get(session_id)
    if iface is None:
        raise HTTPException(404, "会话不存在")

    async def event_generator():
        yield {"event": "status", "data": json.dumps({"status": "generating"})}
        try:
            text, _audio = await asyncio.to_thread(
                iface.select_job, body.job_category, body.include_coding
            )
            agent_state = store.get_state(session_id)
            questions_count = len(agent_state.get("questions", []))
            yield {
                "event": "done",
                "data": json.dumps({
                    "message": text,
                    "questions_count": questions_count,
                }, ensure_ascii=False),
            }
        except Exception as e:
            logger.exception("生成面试题失败")
            yield {
                "event": "error",
                "data": json.dumps({"message": f"生成面试题失败: {e}"}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


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


@router.get("/interview/leetcode/{problem_id}")
async def get_leetcode_problem(problem_id: int):
    """获取 LeetCode 题目完整信息（题面 / 代码模板 / 样例）。"""
    from core.leetcode_manager import get_problem_by_id

    problem = get_problem_by_id(problem_id)
    if not problem:
        raise HTTPException(404, f"未找到 LeetCode #{problem_id}")

    return {
        "id": problem["id"],
        "title": problem.get("title", ""),
        "difficulty": problem.get("difficulty", ""),
        "description": problem.get("description", ""),
        "code_template": problem.get("code_template", "class Solution:\n    pass"),
        "test_cases": problem.get("test_cases", []),
        "slug": problem.get("slug", ""),
        "tags": problem.get("tags", []),
    }


@router.get("/interview/config/job-categories")
async def get_job_categories():
    """获取可选岗位列表。"""
    return {"categories": settings.job_categories}


@router.get("/interview/config/providers")
async def get_providers():
    """获取可用 LLM Provider 列表及当前配置。"""
    from core.llm.providers import PROVIDERS

    key_attr = f"{settings.llm_provider}_api_key"
    has_key = bool(getattr(settings, key_attr, ""))

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
        "current_provider": settings.llm_provider,
        "current_model": settings.llm_model_name or None,
        "has_api_key": has_key,
        "has_voice_key": bool(settings.voice_api_key),
    }


@router.put("/interview/config")
async def update_config(body: dict):
    """运行时更新 LLM / 语音配置，并持久化到 .env。"""
    env_updates: dict[str, str] = {}

    if "provider" in body:
        settings.llm_provider = body["provider"]
        env_updates["LLM_PROVIDER"] = body["provider"]
    if "model" in body:
        settings.llm_model_name = body["model"]
        env_updates["LLM_MODEL_NAME"] = body["model"]
    if "api_key" in body and body["api_key"]:
        key_attr = f"{settings.llm_provider}_api_key"
        setattr(settings, key_attr, body["api_key"])
        env_updates[key_attr.upper()] = body["api_key"]
    if "voice_api_key" in body and body["voice_api_key"]:
        settings.voice_api_key = body["voice_api_key"]
        env_updates["VOICE_API_KEY"] = body["voice_api_key"]

    if env_updates:
        _persist_env(env_updates)

    return {"ok": True}


def _persist_env(updates: dict[str, str]) -> None:
    """将配置变更写入 .env 文件（新增或替换已有行）。"""
    env_path = Path(".env")
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
