"""行为层 | 实体级 Memory 追踪测试。

验证 `_update_memory_for_question` / `_update_memory_for_answer`：
- 切换题目时正确地切换 current_entity
- 旧实体被标记 done
- 候选人回答写入 candidate_answers
"""

from __future__ import annotations


from core.agent.nodes import (
    _init_memory_from_resume,
    _update_memory_for_question,
    _update_memory_for_answer,
    _find_entity_for_question,
)


def test_init_memory_covers_all_resume_entities(sample_resume):
    memory = _init_memory_from_resume(sample_resume)
    entities = memory["entities"]
    # 2 项目 + 1 实习 + 1 教育 = 4
    assert len(entities) == 4
    assert all(r["status"] == "not_started" for r in entities.values())
    assert memory["current_entity"] == ""


def test_ask_question_switches_current_entity(sample_resume):
    memory = _init_memory_from_resume(sample_resume)
    q1 = {
        "id": 1, "question": "介绍下 RepoMind 的整体架构。",
        "dimension": "系统设计", "related_resume_point": "RepoMind",
    }
    memory = _update_memory_for_question(memory, q1)

    assert memory["current_entity"] == "RepoMind"
    assert memory["entities"]["RepoMind"]["status"] == "in_progress"
    assert "系统设计" in memory["covered_dimensions"]

    # 切换到另一项目：旧实体应被置为 done
    q2 = {
        "id": 2, "question": "OfferForge 里的 RAG 是如何实现的？",
        "dimension": "RAG", "related_resume_point": "OfferForge",
    }
    memory = _update_memory_for_question(memory, q2)
    assert memory["current_entity"] == "OfferForge"
    assert memory["entities"]["RepoMind"]["status"] == "done"


def test_candidate_answer_written_into_current_entity(sample_resume):
    memory = _init_memory_from_resume(sample_resume)
    q = {
        "id": 1, "question": "介绍下 RepoMind 的设计。",
        "dimension": "系统设计", "related_resume_point": "RepoMind",
    }
    memory = _update_memory_for_question(memory, q)
    memory = _update_memory_for_answer(
        memory, "RepoMind 采用 LangGraph 驱动多节点 Agent，FAISS 做向量检索。", 0,
    )

    answers = memory["entities"]["RepoMind"]["candidate_answers"]
    assert len(answers) == 1
    assert "LangGraph" in answers[0]


def test_find_entity_fuzzy_match(sample_resume):
    """related_resume_point 大小写/子串 应能模糊命中实体。"""
    memory = _init_memory_from_resume(sample_resume)
    q = {"id": 1, "question": "x", "related_resume_point": "repomind"}  # 小写
    assert _find_entity_for_question(memory, q) == "RepoMind"


def test_general_topic_when_no_entity_match(sample_resume):
    """无关联实体的题目（如算法题）应记入 general_topics。"""
    memory = _init_memory_from_resume(sample_resume)
    q = {"id": 99, "question": "两数之和。", "dimension": "算法",
         "related_resume_point": ""}
    memory = _update_memory_for_question(memory, q)

    assert memory["current_entity"] == ""
    assert len(memory["general_topics"]) == 1
    assert "两数之和" in memory["general_topics"][0]
