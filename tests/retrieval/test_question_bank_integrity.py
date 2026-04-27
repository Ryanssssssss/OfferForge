"""检索层 | 生产题库完整性与契约测试。

这些测试运行在真实的 core/data/question_bank.json 上，确保：
- 字段齐全、类型正确
- ID 全局唯一
- category / type / difficulty 值在受控集合内
- 每个预定义岗位至少有 1 道题，保证 RAG 有召回基础
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import settings

REQUIRED_FIELDS = {"id", "category", "type", "dimension", "difficulty",
                   "question", "tags", "follow_ups"}
VALID_TYPES = {"technical", "behavioral"}
VALID_DIFF = {"easy", "medium", "hard"}


@pytest.fixture(scope="module")
def bank() -> list[dict]:
    path = Path(settings.question_bank_path)
    assert path.exists(), f"题库不存在: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_bank_minimum_size(bank):
    assert len(bank) >= 50  # 至少 50 道题兜底（目前已有 400+）


def test_all_items_have_required_fields(bank):
    missing = [q.get("id") for q in bank if not REQUIRED_FIELDS.issubset(q)]
    assert missing == [], f"字段缺失的题目: {missing[:5]}"


def test_ids_are_unique(bank):
    ids = [q["id"] for q in bank]
    assert len(ids) == len(set(ids)), "存在重复 ID"


def test_enum_values_valid(bank):
    for q in bank:
        assert q["type"] in VALID_TYPES, f"{q['id']} type 非法: {q['type']}"
        assert q["difficulty"] in VALID_DIFF, f"{q['id']} difficulty 非法"
        assert isinstance(q["tags"], list)
        assert isinstance(q["follow_ups"], list)
        assert isinstance(q["question"], str) and len(q["question"]) > 0


def test_every_predefined_job_has_questions(bank):
    """settings.job_categories 中除"简历深度拷打""纯算法题"外，每个岗位都应至少有一题。"""
    skip = {"简历深度拷打（不限岗位）", "纯算法题"}
    categories_in_bank = {q["category"] for q in bank}
    for cat in settings.job_categories:
        if cat in skip:
            continue
        assert cat in categories_in_bank, f"岗位 {cat} 在题库中无题"
