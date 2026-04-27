"""检索层 | 简历解析 → Memory 初始化端到端测试（不解析 PDF）。

通过 stub extract_resume_info 验证 parse_resume_node 能正确把简历实体
灌入 memory，每个项目/实习/教育都应产出独立 EntityRecord。
"""

from __future__ import annotations


def test_parse_resume_node_produces_memory(monkeypatch, sample_resume, tmp_path):
    from core.agent import nodes as nodes_mod

    # 使用 tmp_path 下的不存在文件，避免生成缓存写到仓库
    fake_pdf = tmp_path / "fake.pdf"

    # 让 extract_resume_info 直接返回示例简历
    monkeypatch.setattr(nodes_mod, "extract_resume_info",
                        lambda path: sample_resume, raising=True)

    update = nodes_mod.parse_resume_node({
        "resume_file": str(fake_pdf),
        "session_id": "t",
        "conversation_history": [],
    })

    assert update["interview_phase"] == "job_selection"
    assert update["resume_parsed"]["name"] == "张三"
    entities = update["interview_memory"]["entities"]
    # 2 项目 + 1 实习 + 1 教育
    assert set(entities.keys()) >= {"RepoMind", "OfferForge"}
    assert any(v["entity_type"] == "internship" for v in entities.values())
    assert any(v["entity_type"] == "education" for v in entities.values())


def test_parse_resume_uses_cache_when_available(monkeypatch, sample_resume, tmp_path):
    """第二次解析同一份简历应走缓存，不再调用 extract_resume_info。"""
    from core.agent import nodes as nodes_mod

    fake_pdf = tmp_path / "resume.pdf"
    fake_pdf.write_bytes(b"dummy")

    calls = {"count": 0}

    def _mock_extract(path):
        calls["count"] += 1
        return sample_resume

    monkeypatch.setattr(nodes_mod, "extract_resume_info", _mock_extract, raising=True)

    nodes_mod.parse_resume_node({"resume_file": str(fake_pdf),
                                 "session_id": "t", "conversation_history": []})
    nodes_mod.parse_resume_node({"resume_file": str(fake_pdf),
                                 "session_id": "t", "conversation_history": []})

    assert calls["count"] == 1, "第二次应命中缓存"
