"""语音 API 路由 — STT / TTS。"""

import asyncio
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response

from backend.schemas import TTSRequest, STTResponse
from backend.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/tts")
async def text_to_speech(body: TTSRequest):
    """将文本合成为语音，返回 audio/wav 二进制。"""
    from interfaces.voice_interface import QwenTTS

    tts = QwenTTS()
    if not tts.is_available():
        raise HTTPException(503, "TTS 服务未配置 (缺少 VOICE_API_KEY)")

    audio_bytes = await asyncio.to_thread(tts.synthesize, body.text)
    if not audio_bytes:
        raise HTTPException(500, "语音合成失败")

    return Response(content=audio_bytes, media_type="audio/wav")


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(file: UploadFile = File(...)):
    """语音识别 — 接收 audio 文件，返回文本。"""
    from interfaces.voice_interface import QwenSTT

    stt = QwenSTT()
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(400, "未收到音频数据")

    text = await asyncio.to_thread(stt.transcribe, audio_bytes)
    if not text:
        raise HTTPException(422, "语音识别失败，请重试")

    return STTResponse(text=text)
