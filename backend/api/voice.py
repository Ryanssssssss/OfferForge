"""语音 API 路由 — STT / TTS / 实时 ASR。"""

import asyncio
import json
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from backend.schemas import TTSRequest, STTResponse
from backend.session_store import store
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/tts")
async def text_to_speech(body: TTSRequest):
    """将文本合成为语音，返回 audio/wav 二进制。"""
    from interfaces.voice_interface import QwenTTS, CustomTTS

    # 优先使用自定义远程推理服务
    if CustomTTS.is_available():
        tts = CustomTTS()
    elif QwenTTS.is_available():
        tts = QwenTTS()
    else:
        raise HTTPException(503, "TTS 服务未配置（需要配置 VOICE_API_KEY 或自定义 TTS 地址）")

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


@router.websocket("/asr")
async def realtime_asr(ws: WebSocket):
    """实时语音识别 — 浏览器通过 WebSocket 发送 PCM 音频帧，实时返回识别文本。"""
    await ws.accept()

    if not settings.voice_api_key:
        await ws.send_json({"type": "error", "text": "VOICE_API_KEY 未配置"})
        await ws.close()
        return

    result_queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _put(msg: dict):
        loop.call_soon_threadsafe(result_queue.put_nowait, msg)

    import dashscope
    from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

    dashscope.api_key = settings.voice_api_key

    class _Callback(RecognitionCallback):
        def on_open(self) -> None:
            _put({"type": "open"})

        def on_complete(self) -> None:
            _put({"type": "complete"})

        def on_error(self, message) -> None:
            _put({"type": "error", "text": str(getattr(message, "message", message))})

        def on_event(self, result: RecognitionResult) -> None:
            sentence = result.get_sentence()
            if "text" in sentence:
                is_final = RecognitionResult.is_sentence_end(sentence)
                _put({
                    "type": "final" if is_final else "partial",
                    "text": sentence["text"],
                })

    callback = _Callback()
    recognition = Recognition(
        model="fun-asr-realtime",
        format="pcm",
        sample_rate=16000,
        semantic_punctuation_enabled=False,
        callback=callback,
    )

    await asyncio.to_thread(recognition.start)

    async def _send_results():
        """从 queue 读取识别结果并推送给浏览器。"""
        try:
            while True:
                msg = await result_queue.get()
                await ws.send_json(msg)
                if msg["type"] in ("complete", "error"):
                    break
        except (WebSocketDisconnect, Exception):
            pass

    send_task = asyncio.create_task(_send_results())

    try:
        while True:
            data = await ws.receive_bytes()
            await asyncio.to_thread(recognition.send_audio_frame, data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("ASR WebSocket error: %s", e)
    finally:
        try:
            await asyncio.to_thread(recognition.stop)
        except Exception:
            pass
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass
