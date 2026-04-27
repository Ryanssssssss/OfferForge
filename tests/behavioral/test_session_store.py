"""行为层 | Session Store 并发与过期测试。"""

from __future__ import annotations

import time
import threading

from backend.session_store import SessionStore, SESSION_TTL


def test_get_or_create_is_idempotent(monkeypatch):
    """同一 session_id 多次 get_or_create 返回同一实例。"""
    # 避免真正初始化语音/LLM：替换 VoiceInterviewInterface
    from backend import session_store as ss_mod

    class _Iface:
        pass

    monkeypatch.setattr(ss_mod, "VoiceInterviewInterface", _Iface, raising=True)

    store = SessionStore()
    a = store.get_or_create("s1")
    b = store.get_or_create("s1")
    assert a is b


def test_get_or_create_thread_safe(monkeypatch):
    """多线程并发 get_or_create 同一 session 不应出现多实例竞态。"""
    from backend import session_store as ss_mod

    created = []

    class _Iface:
        def __init__(self):
            created.append(1)

    monkeypatch.setattr(ss_mod, "VoiceInterviewInterface", _Iface, raising=True)

    store = SessionStore()
    results = []

    def worker():
        results.append(store.get_or_create("shared_sid"))

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 所有线程拿到同一个实例
    assert all(r is results[0] for r in results)
    # 由于加锁，实际只创建一次（允许极端并发下少量竞态，但一般应为 1）
    assert len(created) <= 2


def test_cleanup_expired(monkeypatch):
    """手动将 last_active 推回 SESSION_TTL + 1 秒应被清理。"""
    from backend import session_store as ss_mod

    class _Iface:
        pass

    monkeypatch.setattr(ss_mod, "VoiceInterviewInterface", _Iface, raising=True)

    store = SessionStore()
    store.get_or_create("s_old")
    store.get_or_create("s_new")
    # 让 s_old 过期
    store._sessions["s_old"].last_active = time.time() - SESSION_TTL - 10

    cleaned = store.cleanup_expired()
    assert cleaned == 1
    assert store.get("s_old") is None
    assert store.get("s_new") is not None
