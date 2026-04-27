"""安全层 | Session 持久化与过期清理边界测试。

覆盖 core/session_manager.py：
- 损坏 JSON 应被安全跳过而非抛错
- 过期会话在 cleanup 后消失，同时删除关联上传文件
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def test_list_sessions_skips_corrupted(tmp_path, monkeypatch):
    from core import session_manager as sm

    # 指向 tmp
    monkeypatch.setattr(sm, "SESSIONS_DIR", tmp_path / "sessions", raising=True)
    monkeypatch.setattr(sm, "UPLOADS_DIR", tmp_path / "uploads", raising=True)
    sm._ensure_dirs()

    (tmp_path / "sessions" / "ok.json").write_text(
        json.dumps({"_session_id": "ok", "_saved_at": time.time(),
                    "messages": [], "report": None}),
        encoding="utf-8",
    )
    (tmp_path / "sessions" / "broken.json").write_text("not-a-json{", encoding="utf-8")

    sessions = sm.list_sessions()
    ids = [s["session_id"] for s in sessions]
    assert "ok" in ids
    assert "broken" not in ids  # 损坏文件被跳过


def test_cleanup_removes_expired_and_orphan_uploads(tmp_path, monkeypatch):
    from core import session_manager as sm

    sess_dir = tmp_path / "sessions"
    up_dir = tmp_path / "uploads"
    monkeypatch.setattr(sm, "SESSIONS_DIR", sess_dir, raising=True)
    monkeypatch.setattr(sm, "UPLOADS_DIR", up_dir, raising=True)
    # 缩短过期时间以便测试
    monkeypatch.setattr(sm, "SESSION_EXPIRY", 1, raising=True)
    sm._ensure_dirs()

    # 一个已过期会话
    old = sess_dir / "old.json"
    old.write_text(json.dumps({
        "_session_id": "old", "_saved_at": time.time() - 10,
        "messages": [], "report": None,
    }), encoding="utf-8")

    # 一个孤立上传文件（对应 session 不存在、且 mtime 超过 1 天）
    orphan = up_dir / "ghost_xyz.pdf"
    orphan.write_bytes(b"pdf")
    # 手动把 mtime 改为 2 天前
    two_days_ago = time.time() - 86400 * 2
    import os
    os.utime(orphan, (two_days_ago, two_days_ago))

    cleaned = sm.cleanup_expired()
    assert cleaned >= 2
    assert not old.exists()
    assert not orphan.exists()
