"""安全层 | 代码沙箱基础行为测试。

验证 run_code / verify_solution：
- 正常代码 success=True
- 语法错误 → success=False
- 样例测试通过/失败统计正确
"""

from __future__ import annotations

from core.code_runner import run_code, verify_solution


def test_run_code_simple_success():
    result = run_code("print('hello')")
    assert result["success"] is True
    assert result["stdout"] == "hello"
    assert result["returncode"] == 0


def test_run_code_syntax_error():
    result = run_code("def bad(: pass")
    assert result["success"] is False
    assert "SyntaxError" in result["stderr"] or result["returncode"] != 0


def test_verify_solution_all_passed():
    """Solution.twoSum 正确实现应能通过所有样例。"""
    code = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        seen = {}\n"
        "        for i, n in enumerate(nums):\n"
        "            if target - n in seen:\n"
        "                return [seen[target - n], i]\n"
        "            seen[n] = i\n"
        "        return []\n"
    )
    problem = {
        "code_template": "class Solution:\n    def twoSum(self, nums, target):\n        pass\n",
        "test_cases": [
            "[2,7,11,15]\n9",
            "[3,2,4]\n6",
        ],
    }
    result = verify_solution(code, problem, timeout=10)
    assert result["success"] is True
    assert result["passed"] == result["total"] == 2


def test_verify_solution_compile_error_fails_fast():
    """编译失败应直接返回 success=False，passed=0。"""
    problem = {
        "code_template": "class Solution:\n    def solve(self):\n        pass\n",
        "test_cases": ["1"],
    }
    result = verify_solution("class Solution\n  def solve(self): pass", problem)
    assert result["success"] is False
    assert result["passed"] == 0
