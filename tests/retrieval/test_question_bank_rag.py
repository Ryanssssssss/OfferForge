"""检索层 | RAG 题库检索测试。

验证：
- 岗位过滤生效（只召回 target category + 通用）
- top_k 截断正确
- fallback 向量化方案在没有 sentence-transformers 时仍能返回
"""

from __future__ import annotations

import importlib


def _reload_rag_with_bank(monkeypatch, bank_path):
    """把 RAG 模块的题库路径指到自定义题库，并重置模块级缓存。"""
    from config.settings import settings
    monkeypatch.setattr(settings, "question_bank_path", str(bank_path), raising=False)

    import core.rag.question_bank_rag as rag_mod
    importlib.reload(rag_mod)
    # 强制使用 fallback 模型，避免加载真实 embedding（离线）
    rag_mod._model = "fallback"
    rag_mod._questions = []
    rag_mod._embeddings_cache = None
    return rag_mod


def test_search_filters_by_job_category(monkeypatch, sample_question_bank):
    rag = _reload_rag_with_bank(monkeypatch, sample_question_bank)

    results = rag.search_questions(
        job_category="后端开发", resume_context="Python Redis", top_k=4,
    )
    # 返回 4 道，都应来自"后端开发"或"通用"
    assert len(results) == 4
    for q in results:
        assert q["category"] in {"后端开发", "通用"}


def test_search_top_k_respected(monkeypatch, sample_question_bank):
    rag = _reload_rag_with_bank(monkeypatch, sample_question_bank)

    results = rag.search_questions(job_category="前端开发", top_k=2)
    assert len(results) == 2


def test_search_falls_back_when_category_missing(monkeypatch, sample_question_bank):
    """未知岗位时应回退到全量候选池，而不是返回空。"""
    rag = _reload_rag_with_bank(monkeypatch, sample_question_bank)

    results = rag.search_questions(job_category="不存在的岗位", top_k=3)
    assert len(results) == 3  # 退回全量


def test_empty_bank_returns_empty(monkeypatch, tmp_path):
    """题库文件不存在时应返回空列表且不崩溃。"""
    from config.settings import settings
    monkeypatch.setattr(settings, "question_bank_path", str(tmp_path / "nope.json"), raising=False)

    import core.rag.question_bank_rag as rag_mod
    importlib.reload(rag_mod)
    rag_mod._questions = []
    rag_mod._embeddings_cache = None

    assert rag_mod.search_questions(job_category="后端开发") == []
