"""文本交互接口。

封装 InterviewAgent 的交互逻辑，提供简洁的文本输入/输出接口。
供 Streamlit UI 和语音接口调用。
"""

import logging
from typing import Any

from core.agent.graph import InterviewAgent

logger = logging.getLogger(__name__)


class TextInterface:
    """面试文本交互接口。

    用法：
        interface = TextInterface()
        greeting = interface.start_interview("resume.pdf")
        intro = interface.select_job("后端开发")
        response = interface.send_message("我在这个项目中负责...")
        report = interface.get_report()
    """

    def __init__(self):
        self._agent = InterviewAgent()

    @property
    def is_finished(self) -> bool:
        return self._agent.is_finished

    @property
    def current_phase(self) -> str:
        return self._agent.current_phase

    @property
    def last_output(self) -> str:
        """获取最新一次 Thinker 输出文本（供 TTS 消费）。"""
        return self._agent.thinker_output

    def start_interview(self, resume_file: str, session_id: str = "default") -> str:
        """开始面试：上传简历。

        Args:
            resume_file: PDF 简历文件路径。
            session_id: 会话标识。

        Returns:
            面试官的开场白。
        """
        logger.info("开始新面试会话: %s", session_id)
        return self._agent.start(resume_file, session_id)

    def select_job(self, job_category: str, include_coding: bool = True) -> str:
        """选择目标岗位。"""
        logger.info("选择岗位: %s (代码题: %s)", job_category, include_coding)
        return self._agent.select_job(job_category, include_coding=include_coding)

    def send_message(self, text: str) -> str:
        """发送候选人的回答文本。

        Args:
            text: 候选人回答（可以是用户直接输入，也可以是 STT 转换后的文本）。

        Returns:
            面试官回应的纯文本（可直接传给 TTS）。
        """
        if self._agent.is_finished:
            return "面试已经结束了，请查看反馈报告。"

        return self._agent.submit_answer(text)

    def get_report(self) -> dict[str, Any]:
        """获取面试反馈报告。"""
        return self._agent.get_report()

    def get_conversation_history(self) -> list[dict[str, str]]:
        """获取完整对话历史。"""
        return self._agent.get_conversation_history()

    def get_current_progress(self) -> dict[str, Any]:
        """获取当前面试进度信息。"""
        state = self._agent.state
        questions = state.get("questions", [])
        current_idx = state.get("current_question_idx", 0)
        return {
            "phase": self.current_phase,
            "total_questions": len(questions),
            "current_question": min(current_idx + 1, len(questions)),
            "is_finished": self.is_finished,
        }

    def reset(self) -> None:
        """重置面试。"""
        self._agent.reset()
        logger.info("面试已重置")
