"""
run_code.py — 代码执行工具

将用户的代码交给沙箱执行引擎，返回结果。
这是本项目最核心的工具——CodeAct 的入口。
"""
from typing import Optional

from nano_agent_sandbox.sandbox.executor import CodeExecutor

# 全局单例，由 main.py 初始化后注入
_executor: Optional[CodeExecutor] = None


def init(executor: CodeExecutor):
    """注入执行引擎实例"""
    global _executor
    _executor = executor


def run_code(code: str) -> str:
    """
    在沙箱中执行 Python 代码。

    Args:
        code: Python 代码字符串

    Returns:
        执行结果（成功输出 or 错误信息）
    """
    if _executor is None:
        return "Error: Code executor not initialized."
    result = _executor.execute(code)
    return result.output
