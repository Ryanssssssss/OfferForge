"""Pydantic request / response 模型。"""

from pydantic import BaseModel


# ── Interview ──

class SelectJobRequest(BaseModel):
    job_category: str
    include_coding: bool = True


class SubmitAnswerRequest(BaseModel):
    answer: str


class RunCodeRequest(BaseModel):
    code: str
    language: str = "python3"
    leetcode_id: int


class StartInterviewResponse(BaseModel):
    session_id: str
    greeting: str


class SelectJobResponse(BaseModel):
    message: str
    questions_count: int


class InterviewStatusResponse(BaseModel):
    phase: str
    progress: dict
    is_finished: bool
    current_question: dict | None = None


class RunCodeResponse(BaseModel):
    success: bool
    passed: int
    total: int
    output: str
    error: str


class ReportResponse(BaseModel):
    report: dict
    conversation_history: list[dict]


# ── Voice ──

class TTSRequest(BaseModel):
    text: str


class STTResponse(BaseModel):
    text: str


# ── Sessions ──

class SessionItem(BaseModel):
    session_id: str
    candidate_name: str = ""
    job_category: str = ""
    saved_at: float | None = None
    has_report: bool = False


# ── Config ──

class ProviderInfo(BaseModel):
    id: str
    name: str
    models: list[str]
    default_model: str
