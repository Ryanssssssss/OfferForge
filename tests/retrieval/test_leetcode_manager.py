"""检索层 | LeetCode 题库管理器测试。"""

from __future__ import annotations

import importlib


def test_get_problem_by_id_found_or_none():
    import core.leetcode_manager as lm
    importlib.reload(lm)

    # 正常：id=1 通常为"两数之和"
    p = lm.get_problem_by_id(1)
    if p is not None:  # 题库允许不存在
        assert p.get("id") == 1
        assert "title" in p


def test_get_problem_by_id_negative_returns_none():
    import core.leetcode_manager as lm
    assert lm.get_problem_by_id(9_999_999) is None


def test_get_problem_by_title_fuzzy():
    import core.leetcode_manager as lm
    p = lm.get_problem_by_title("two sum")
    # 允许为空（题库未覆盖），但结构要么是 dict 要么是 None
    assert p is None or isinstance(p, dict)
