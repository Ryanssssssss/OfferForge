"""行为层 | Agent 生命周期与状态机测试。

目标：验证 InterviewAgent 按照
parse_resume → job_selection → ready_to_ask → waiting_answer → ... → finished
的状态流转，且各阶段字段符合契约。
"""

from __future__ import annotations


def test_start_enters_job_selection_phase(prepared_agent):
    """start() 之后应处于 job_selection 阶段，需要用户输入岗位。"""
    state = prepared_agent.state
    assert state["interview_phase"] == "job_selection"
    assert state["needs_input"] is True
    # 简历已解析
    assert state["resume_parsed"]["name"] == "张三"
    # Memory 按简历实体初始化：2 个项目 + 1 个实习 + 1 个教育 = 4 实体
    entities = state["interview_memory"]["entities"]
    assert len(entities) == 4
    assert "RepoMind" in entities
    # 欢迎语写入对话历史
    assert prepared_agent.get_conversation_history()[0]["role"] == "interviewer"


def test_select_job_generates_questions_and_asks_first(prepared_agent):
    """选岗后应生成题目并立即提出第 1 题。"""
    prepared_agent.select_job("后端开发", include_coding=False)

    state = prepared_agent.state
    assert state["job_category"] == "后端开发"
    assert len(state["questions"]) >= 1
    assert state["current_question_idx"] == 0
    assert state["interview_phase"] == "waiting_answer"
    assert state["needs_input"] is True


def test_full_interview_flow_reaches_finished(prepared_agent):
    """提交回答直至所有题目结束，最终应 is_finished=True 且有报告。"""
    prepared_agent.select_job("后端开发", include_coding=False)
    total = len(prepared_agent.state["questions"])

    for i in range(total):
        prepared_agent.submit_answer(f"这是第 {i+1} 题的详细回答，包含了项目背景与技术栈。")

    assert prepared_agent.is_finished is True
    assert prepared_agent.current_phase == "finished"
    report = prepared_agent.get_report()
    assert report["overall_score"] == 78
    assert report["overall_rating"] == "B+"


def test_reset_clears_state(prepared_agent):
    prepared_agent.select_job("后端开发", include_coding=False)
    prepared_agent.reset()
    assert prepared_agent.state == {}
    assert prepared_agent.current_phase == "init"
    assert prepared_agent.is_finished is False
