"""语音交互接口。

TTS：使用 dashscope SDK 的 qwen3-tts-flash-realtime（WebSocket 实时语音合成）
STT：使用 Qwen3-Omni 的 OpenAI 兼容模式（语音转文字）
"""

import base64
import io
import logging
import threading
from typing import Any

import numpy as np
import soundfile as sf

from config.settings import settings
from interfaces.text_interface import TextInterface

logger = logging.getLogger(__name__)


class QwenTTS:
    """基于 dashscope SDK 的 Qwen3-TTS 语音合成。

    使用 qwen3-tts-flash-realtime 模型，WebSocket 实时合成。
    """

    def __init__(self, voice: str | None = None):
        self._voice = voice or settings.voice_name

    def synthesize(self, text: str, speed: float = 1.25) -> bytes:
        """将文本合成为 PCM 音频，返回 WAV 字节。

        Args:
            text: 要合成的文本。

        Returns:
            WAV 格式音频字节。空字节表示失败。
        """
        try:
            import dashscope
            from dashscope.audio.qwen_tts_realtime import (
                QwenTtsRealtime,
                QwenTtsRealtimeCallback,
                AudioFormat,
            )
        except ImportError:
            logger.error("dashscope 未安装，请运行: pip install dashscope")
            return b""

        # 设置 API Key
        dashscope.api_key = settings.voice_api_key
        if not dashscope.api_key:
            logger.error("VOICE_API_KEY 未配置")
            return b""

        # 收集音频数据的回调
        audio_chunks: list[bytes] = []
        complete_event = threading.Event()
        error_msg = None

        class _Callback(QwenTtsRealtimeCallback):
            def on_open(self) -> None:
                pass

            def on_close(self, close_status_code, close_msg) -> None:
                complete_event.set()

            def on_error(self, message) -> None:
                # WebSocket 正常关闭 (code 1000 "Bye") 不是真 error，忽略
                msg_str = str(message)
                if "Bye" in msg_str or "\\x03\\xe8" in msg_str or "1000" in msg_str:
                    return
                nonlocal error_msg
                error_msg = msg_str
                logger.error("TTS WebSocket error: %s", msg_str)

            def on_event(self, response: dict) -> None:
                nonlocal error_msg
                try:
                    resp_type = response.get("type", "")
                    if resp_type == "response.audio.delta":
                        chunk_b64 = response.get("delta", "")
                        if chunk_b64:
                            audio_chunks.append(base64.b64decode(chunk_b64))
                    elif resp_type == "session.finished":
                        complete_event.set()
                except Exception as e:
                    error_msg = str(e)
                    complete_event.set()

        callback = _Callback()

        try:
            tts = QwenTtsRealtime(
                model="qwen3-tts-instruct-flash-realtime",
                callback=callback,
                url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
            )

            tts.connect()
            tts.update_session(
                voice=self._voice,
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                instructions="语速较快，语气专业干练，像资深面试官一样沉稳有力。",
                optimize_instructions=True,
                speed=speed,
                mode="server_commit",
            )

            # 分句发送文本（避免一次发太长）
            chunks = self._split_text(text)
            for chunk in chunks:
                tts.append_text(chunk)

            tts.finish()
            complete_event.wait(timeout=30)

            if error_msg:
                logger.error("TTS 合成错误: %s", error_msg)
                return b""

            if not audio_chunks:
                logger.warning("TTS 未返回音频数据")
                return b""

            # 合并 PCM 并转为 WAV
            pcm_data = b"".join(audio_chunks)
            return self._pcm_to_wav(pcm_data, sample_rate=24000)

        except Exception as e:
            logger.error("TTS 失败: %s", e)
            return b""

    @staticmethod
    def _split_text(text: str, max_len: int = 100) -> list[str]:
        """按标点分句，防止单次发送过长。"""
        if len(text) <= max_len:
            return [text]

        chunks = []
        current = ""
        for char in text:
            current += char
            if char in "。！？；，、.!?;," and len(current) >= 20:
                chunks.append(current)
                current = ""
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
        """PCM 16bit mono → WAV。"""
        try:
            audio_np = np.frombuffer(pcm_data, dtype=np.int16)
            buffer = io.BytesIO()
            sf.write(buffer, audio_np, samplerate=sample_rate, format="WAV")
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            logger.error("PCM → WAV 转换失败: %s", e)
            return b""

    @staticmethod
    def is_available() -> bool:
        """检查 TTS 是否可用。"""
        return bool(settings.voice_api_key)


class QwenSTT:
    """基于 Qwen3-Omni OpenAI 兼容模式的语音识别。"""

    def __init__(self):
        self._api_key = settings.voice_api_key
        self._base_url = settings.voice_base_url
        self._model = "qwen3-omni-flash"  # Omni 模型用于 STT

    def transcribe(self, audio_bytes: bytes) -> str:
        """语音转文本。

        Args:
            audio_bytes: WAV 格式音频字节。

        Returns:
            识别出的文本。
        """
        if not self._api_key:
            logger.error("VOICE_API_KEY 未配置")
            return ""

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key, base_url=self._base_url)

            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            completion = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "将语音准确转写为文本，只输出转写内容。",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": f"data:audio/wav;base64,{audio_b64}",
                                    "format": "wav",
                                },
                            },
                            {"type": "text", "text": "转写这段语音。"},
                        ],
                    },
                ],
                modalities=["text"],
                stream=True,
                stream_options={"include_usage": True},
            )

            text = ""
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    text += chunk.choices[0].delta.content

            logger.info("STT: %s", text[:100] if text else "(空)")
            return text.strip()

        except Exception as e:
            logger.error("STT 失败: %s", e)
            return ""


class VoiceInterviewInterface:
    """语音面试交互接口。

    整合 TextInterface（Agent 逻辑）+ QwenTTS + QwenSTT。
    """

    def __init__(self):
        self._text_interface = TextInterface()
        self._tts = QwenTTS() if QwenTTS.is_available() else None
        self._stt = QwenSTT() if QwenTTS.is_available() else None

    @property
    def voice_available(self) -> bool:
        return self._tts is not None

    @property
    def text_interface(self) -> TextInterface:
        return self._text_interface

    @property
    def is_finished(self) -> bool:
        return self._text_interface.is_finished

    def _get_speed(self) -> float:
        """从 streamlit session_state 获取用户设置的语速。"""
        try:
            import streamlit as st
            return st.session_state.get("voice_speed", 1.25)
        except Exception:
            return 1.25

    def start_interview(self, resume_file: str, session_id: str = "default") -> tuple[str, bytes]:
        """开始面试，返回 (文本, 音频)。"""
        text = self._text_interface.start_interview(resume_file, session_id)
        audio = self._tts.synthesize(text, speed=self._get_speed()) if self._tts else b""
        return text, audio

    def select_job(self, job_category: str, include_coding: bool = True) -> tuple[str, bytes]:
        """选择岗位，返回 (文本, 音频)。"""
        text = self._text_interface.select_job(job_category, include_coding=include_coding)
        audio = self._tts.synthesize(text, speed=self._get_speed()) if self._tts else b""
        return text, audio

    def process_text_input(self, text: str) -> tuple[str, bytes]:
        """处理文本输入，返回 (面试官文本, 音频)。"""
        response = self._text_interface.send_message(text)
        audio = self._tts.synthesize(response, speed=self._get_speed()) if self._tts else b""
        return response, audio

    def process_voice_input(self, audio_bytes: bytes) -> tuple[str, str, bytes]:
        """处理语音输入，返回 (用户文本, 面试官文本, 面试官音频)。"""
        if not self._stt or not self._tts:
            return "", "语音服务未配置", b""

        user_text = self._stt.transcribe(audio_bytes)
        if not user_text:
            return "", "没听清，请再说一次。", b""

        response = self._text_interface.send_message(user_text)
        audio = self._tts.synthesize(response, speed=self._get_speed())
        audio = self._tts.synthesize(response)

        return user_text, response, audio

    def get_report(self) -> dict[str, Any]:
        return self._text_interface.get_report()

    def get_conversation_history(self) -> list[dict[str, str]]:
        return self._text_interface.get_conversation_history()

    def get_current_progress(self) -> dict[str, Any]:
        return self._text_interface.get_current_progress()

    def reset(self) -> None:
        self._text_interface.reset()
