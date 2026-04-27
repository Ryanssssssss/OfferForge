"""pytest 共享 fixtures。

设计原则：
- 所有 LLM / Embedding 调用使用 monkeypatch 替换为确定性桩，保证离线可跑。
- 通过 fixture 返回可复用的示例简历、题库片段、Agent 工厂等。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# 保证根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------- 示例简历 ----------

@pytest.fixture
def sample_resume() -> dict[str, Any]:
    """一份典型的结构化简历（覆盖项目/实习/论文/教育）。"""
    return {
        "name": "张三",
        "education": [
            {"school": "清华大学", "major": "计算机科学", "degree": "硕士"},
        ],
        "skills": ["Python", "Java", "Redis", "MySQL"],
        "projects": [
            {
                "name": "RepoMind",
                "description": "基于 LangGraph 的代码仓库问答系统",
                "tech_stack": ["Python", "LangGraph", "FAISS"],
                "highlights": ["RAG 检索", "多轮对话"],
            },
            {
                "name": "OfferForge",
                "description": "AI 简历面试教练",
                "tech_stack": ["FastAPI", "Next.js"],
                "highlights": ["LangGraph Agent"],
            },
        ],
        "internships": [
            {
                "company": "腾讯IEG",
                "role": "后端开发实习生",
                "duration": "2024.06-2024.09",
                "responsibilities": ["服务端接口开发"],
            },
        ],
        "publications": [],
        "research": [],
    }


# ---------- 示例题库 ----------

@pytest.fixture
def sample_question_bank(tmp_path: Path) -> Path:
    """写入一个 15 题的示例题库到 tmp_path，返回文件路径。"""
    bank: list[dict] = []
    for cat in ["后端开发", "前端开发", "算法工程师"]:
        for i in range(4):
            bank.append({
                "id": f"test_{cat}_{i}",
                "category": cat,
                "type": "technical",
                "dimension": f"{cat}-维度{i}",
                "difficulty": ["easy", "medium", "hard"][i % 3],
                "question": f"{cat} 第 {i} 道题: 请谈谈 {cat} 的核心点。",
                "tags": [cat, f"tag{i}"],
                "follow_ups": ["追问A", "追问B"],
            })
    # 通用题
    for i in range(3):
        bank.append({
            "id": f"test_general_{i}",
            "category": "通用",
            "type": "behavioral",
            "dimension": "软技能",
            "difficulty": "medium",
            "question": f"通用题 {i}: 介绍一下你自己的优势。",
            "tags": ["通用"],
            "follow_ups": ["请举一个具体例子"],
        })

    p = tmp_path / "question_bank.json"
    p.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ---------- Mock LLM ----------

class FakeThinker:
    """离线 Thinker 桩：按方法预设返回值，不发网络请求。"""

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []
        # 默认返回：面试官话术
        self.text_response = "[面试官] 好的，请你介绍一下这个项目的整体设计。"
        # think_json_with_template 的默认 JSON 返回（追问判断）
        self.json_response: Any = {
            "need_followup": False,
            "terminate_interview": False,
            "response": "回答不错，我们进入下一题。",
        }

    def think(self, prompt: str, system_prompt: str | None = None) -> str:
        self.calls.append(("think", (prompt,), {"system_prompt": system_prompt}))
        return self.text_response

    def think_json(self, prompt: str, system_prompt: str | None = None):
        self.calls.append(("think_json", (prompt,), {"system_prompt": system_prompt}))
        return self.json_response

    def think_with_template(self, template: str, variables: dict, system_prompt: str | None = None) -> str:
        self.calls.append(("think_with_template", (template,), {"variables": variables}))
        return self.text_response

    def think_json_with_template(self, template: str, variables: dict, system_prompt: str | None = None):
        self.calls.append(("think_json_with_template", (template,), {"variables": variables}))
        return self.json_response


@pytest.fixture
def fake_thinker(monkeypatch) -> FakeThinker:
    """用 FakeThinker 替换所有模块中引用的 thinker 单例。"""
    fake = FakeThinker()
    # 覆盖所有已经 from core.llm.thinker import thinker 的模块
    import core.llm.thinker as thinker_mod
    import core.agent.nodes as nodes_mod
    import core.interview.question_gen as qg_mod
    import core.interview.evaluator as ev_mod
    import core.interview.reporter as rp_mod

    monkeypatch.setattr(thinker_mod, "thinker", fake, raising=True)
    monkeypatch.setattr(nodes_mod, "thinker", fake, raising=True)
    monkeypatch.setattr(qg_mod, "thinker", fake, raising=True)
    monkeypatch.setattr(ev_mod, "thinker", fake, raising=True)
    monkeypatch.setattr(rp_mod, "thinker", fake, raising=True)
    return fake


# ---------- Agent fixture ----------

@pytest.fixture
def prepared_agent(fake_thinker, sample_resume, monkeypatch):
    """返回一个已走完 parse_resume 的 Agent。跳过真正的 PDF 解析与 LLM 调用。"""
    from core.agent.graph import InterviewAgent
    import core.agent.nodes as nodes_mod

    # Stub extract_resume_info：直接返回示例简历，不做 PDF 解析
    monkeypatch.setattr(nodes_mod, "extract_resume_info", lambda path: sample_resume, raising=True)

    # Stub evaluator.evaluate_answer & evaluate_for_followup
    def _stub_eval_answer(**kwargs):
        return {
            "scores": {"内容": 8, "表达": 7},
            "overall_score": 7.5,
            "strengths": ["思路清晰"],
            "improvements": ["可补充数据量化"],
        }

    def _stub_eval_followup(**kwargs):
        return {
            "need_followup": False,
            "terminate_interview": False,
            "response": "明白了，我们进入下一题。",
        }

    from core.agent.nodes import _evaluator, _reporter, _question_gen
    monkeypatch.setattr(_evaluator, "evaluate_answer", _stub_eval_answer, raising=True)
    monkeypatch.setattr(_evaluator, "evaluate_for_followup", _stub_eval_followup, raising=True)

    # Stub reporter
    monkeypatch.setattr(
        _reporter, "generate_report",
        lambda **kwargs: {
            "overall_score": 78,
            "overall_rating": "B+",
            "per_question": [],
            "summary": "综合表现中上。",
        },
        raising=True,
    )

    # Stub QuestionGenerator.generate：返回 3 道固定题目，避开 RAG/LLM
    def _stub_gen(self, job_category, resume_data=None, num_questions=3, include_coding=False):
        return [
            {
                "id": i + 1,
                "question": f"关于 {name} 的问题：请详细说明。",
                "type": "technical",
                "dimension": "项目深度",
                "difficulty": "medium",
                "related_resume_point": name,
            }
            for i, name in enumerate([p["name"] for p in (resume_data or {}).get("projects", [])][:3])
        ] or [
            {
                "id": 1,
                "question": "请做一下自我介绍。",
                "type": "behavioral",
                "dimension": "综合",
                "difficulty": "easy",
                "related_resume_point": "",
            }
        ]

    from core.interview.question_gen import QuestionGenerator
    monkeypatch.setattr(QuestionGenerator, "generate", _stub_gen, raising=True)

    # 禁用 LeetCode 追加（include_coding=True 时才会调用）；原函数是 @staticmethod
    monkeypatch.setattr(
        QuestionGenerator, "_pick_leetcode_question",
        staticmethod(lambda: None), raising=True,
    )

    agent = InterviewAgent()
    agent.start(resume_file="/tmp/fake_resume.pdf", session_id="test_session")
    return agent
