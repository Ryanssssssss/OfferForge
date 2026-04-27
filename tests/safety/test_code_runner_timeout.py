"""安全层 | 代码运行超时保护。

验证：用户代码陷入死循环时应在 timeout 秒内被强制终止，不会拖死后端。
"""

from __future__ import annotations

import time

from core.code_runner import run_code


def test_infinite_loop_terminated_by_timeout():
    start = time.time()
    result = run_code("while True:\n    pass", timeout=2)
    elapsed = time.time() - start

    # 应在 timeout + 合理开销内结束
    assert elapsed < 5, f"超时保护失效，用时 {elapsed:.2f}s"
    assert result["success"] is False
    assert "超时" in result["stderr"] or result["returncode"] == -1


def test_cpu_heavy_computation_timeout():
    """大计算量任务也应被超时杀掉。"""
    code = "s = 0\nfor i in range(10**12):\n    s += i"
    start = time.time()
    result = run_code(code, timeout=1)
    elapsed = time.time() - start
    assert elapsed < 4
    assert result["success"] is False
