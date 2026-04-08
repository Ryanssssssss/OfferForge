"""面试 Agent 核心 —— 基于 LangGraph 节点的分步交互控制。

面试是多轮人机交互，每一步需要等待用户输入后才能继续。
因此采用「手动调度节点」模式：Agent 维护全局状态，按面试阶段
调用对应的节点函数，每次返回后暂停等待外部输入。

LangGraph StateGraph 保留用于定义流程图结构，可用于可视化和未来扩展。
"""

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from core.agent.states import InterviewState
from core.agent.nodes import (
    parse_resume_node,
    generate_questions_node,
    ask_question_node,
    process_answer_node,
    generate_report_node,
)

logger = logging.getLogger(__name__)


def build_interview_graph() -> StateGraph:
    """构建面试流程状态图（供可视化和未来扩展使用）。"""
    graph = StateGraph(InterviewState)

    graph.add_node("parse_resume", parse_resume_node)
    graph.add_node("generate_questions", generate_questions_node)
    graph.add_node("ask_question", ask_question_node)
    graph.add_node("process_answer", process_answer_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("parse_resume")
    graph.add_edge("parse_resume", END)
    graph.add_edge("generate_questions", "ask_question")
    graph.add_edge("ask_question", END)
    graph.add_edge("generate_report", END)

    return graph.compile()


class InterviewAgent:
    """面试 Agent，通过手动调度节点函数实现分步交互。

    流程：
        start()         → parse_resume_node → 等待岗位选择
        select_job()    → generate_questions_node + ask_question_node → 等待回答
        submit_answer() → process_answer_node → [追问等待 / ask_question / generate_report]
    """

    def __init__(self):
        self._state: InterviewState = {}

    @property
    def state(self) -> InterviewState:
        return self._state

    @property
    def is_finished(self) -> bool:
        return self._state.get("is_finished", False)

    @property
    def current_phase(self) -> str:
        return self._state.get("interview_phase", "init")

    @property
    def thinker_output(self) -> str:
        """获取最新的 Thinker 文本输出（供语音 TTS 消费）。"""
        return self._state.get("thinker_output", "")

    def _apply_update(self, update: dict[str, Any]) -> None:
        """将节点返回的增量更新合并到全局状态。"""
        self._state.update(update)

    def start(self, resume_file: str, session_id: str = "default") -> str:
        """启动面试：解析简历。"""
        self._state = {
            "resume_file": resume_file,
            "session_id": session_id,
            "conversation_history": [],
            "evaluations": [],
            "current_question_idx": 0,
            "follow_up_count": 0,
            "current_question_answers": [],
            "needs_input": False,
            "is_finished": False,
        }

        update = parse_resume_node(self._state)
        self._apply_update(update)
        return self.thinker_output

    def select_job(self, job_category: str, include_coding: bool = True) -> str:
        """用户选择岗位后，生成面试题并提出第一个问题。"""
        self._state["job_category"] = job_category
        self._state["include_coding"] = include_coding

        # 生成题目
        update = generate_questions_node(self._state)
        self._apply_update(update)

        # 立即提出第一个问题
        update = ask_question_node(self._state)
        self._apply_update(update)
        return self.thinker_output

    def submit_answer(self, answer: str) -> str:
        """提交候选人回答，返回面试官的回应。"""
        self._state["current_answer"] = answer

        # 处理回答（评估 + 决定追问/下一题/结束）
        update = process_answer_node(self._state)
        self._apply_update(update)

        phase = self._state.get("interview_phase", "")

        if phase == "ready_to_ask":
            # 进入下一题
            update = ask_question_node(self._state)
            self._apply_update(update)
        elif phase == "generate_report":
            # 生成报告
            update = generate_report_node(self._state)
            self._apply_update(update)
        # else: waiting_answer（追问，等待用户下一次输入）

        return self.thinker_output

    def get_report(self) -> dict[str, Any]:
        """获取面试反馈报告。"""
        return self._state.get("final_report", {})

    def get_conversation_history(self) -> list[dict[str, str]]:
        """获取完整对话历史。"""
        return self._state.get("conversation_history", [])

    def reset(self) -> None:
        """重置面试状态。"""
        self._state = {}
