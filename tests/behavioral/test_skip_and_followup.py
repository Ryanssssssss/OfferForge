"""行为层 | 跳过 & 追问分支测试。

验证 process_answer_node 对特殊输入的处理：
- 候选人说"不会/跳过/下一题" → 直接进下一题，不调用 LLM 评估
- 超出 max_follow_ups 时不再追问
"""

from __future__ import annotations

from core.agent.nodes import process_answer_node


def _base_state(questions_count: int = 2) -> dict:
    questions = [
        {
            "id": i + 1, "question": f"题目{i+1}", "type": "technical",
            "dimension": "综合", "difficulty": "medium",
            "related_resume_point": "",
        }
        for i in range(questions_count)
    ]
    return {
        "questions": questions,
        "current_question_idx": 0,
        "current_answer": "",
        "follow_up_count": 0,
        "max_follow_ups": 3,
        "conversation_history": [],
        "evaluations": [],
        "current_question_answers": [],
        "job_category": "后端开发",
        "session_id": "t",
        "interview_memory": {
            "entities": {}, "current_entity": "",
            "general_topics": [], "covered_dimensions": [],
        },
    }


def test_skip_keyword_bypasses_llm(fake_thinker):
    """输入'跳过'应直接推进到下一题，且不调用 LLM。"""
    state = _base_state(2)
    state["current_answer"] = "跳过"

    update = process_answer_node(state)

    # LLM 应未被调用
    assert fake_thinker.calls == []
    # 下一题，且评分 0
    assert update["current_question_idx"] == 1
    assert update["interview_phase"] == "ready_to_ask"
    assert update["evaluations"][-1]["overall_score"] == 0


def test_skip_at_last_question_triggers_report(fake_thinker):
    """最后一题跳过应进入报告阶段。"""
    state = _base_state(1)
    state["current_answer"] = "不会"

    update = process_answer_node(state)
    assert update["interview_phase"] == "generate_report"


def test_long_answer_containing_skip_word_is_not_skip(fake_thinker, monkeypatch):
    """超过长度阈值的正常回答即便含'跳过'字样也不算跳过。"""
    # 防止真正调用 evaluator
    from core.agent import nodes as nodes_mod
    monkeypatch.setattr(
        nodes_mod._evaluator, "evaluate_for_followup",
        lambda **kw: {"need_followup": False, "terminate_interview": False,
                      "response": "好"}, raising=True,
    )
    monkeypatch.setattr(
        nodes_mod._evaluator, "evaluate_answer",
        lambda **kw: {"scores": {}, "overall_score": 7,
                      "strengths": [], "improvements": []}, raising=True,
    )

    state = _base_state(2)
    state["current_answer"] = "我的完整回答：我不会跳过任何细节，以下会详细展开……" * 2

    update = process_answer_node(state)
    # 正常评估流程，得分 7 非 0
    assert update["evaluations"][-1]["overall_score"] == 7


def test_followup_capped_by_max(fake_thinker, monkeypatch):
    """当 follow_up_count >= max_follow_ups 时，即便 LLM 建议追问也不再追问。"""
    from core.agent import nodes as nodes_mod
    monkeypatch.setattr(
        nodes_mod._evaluator, "evaluate_for_followup",
        lambda **kw: {"need_followup": True, "terminate_interview": False,
                      "response": "再深入说说。"}, raising=True,
    )
    monkeypatch.setattr(
        nodes_mod._evaluator, "evaluate_answer",
        lambda **kw: {"scores": {}, "overall_score": 7,
                      "strengths": [], "improvements": []}, raising=True,
    )

    state = _base_state(2)
    state["current_answer"] = "我觉得设计上采用了分层架构，细节请展开。"
    state["follow_up_count"] = 3  # 已达上限
    state["max_follow_ups"] = 3

    update = process_answer_node(state)
    # 不应再停留在 waiting_answer
    assert update["interview_phase"] in {"ready_to_ask", "generate_report"}
    assert update["current_question_idx"] == 1
