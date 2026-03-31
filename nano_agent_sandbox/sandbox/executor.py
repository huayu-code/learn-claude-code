"""
executor.py — 代码执行引擎（门面层）

对外提供统一的 execute(code) 接口，内部委托给具体沙箱实现。
目前使用 SubprocessSandbox，未来可以切换为 DockerSandbox。
"""
from pathlib import Path
from typing import Optional

from nano_agent_sandbox.sandbox.subprocess_sandbox import SubprocessSandbox, ExecutionResult
from nano_agent_sandbox.config import SANDBOX_WORKDIR


class CodeExecutor:
    """代码执行引擎 — 统一门面"""

    def __init__(self, workdir: Optional[Path] = None):
        self.sandbox = SubprocessSandbox(workdir=workdir or SANDBOX_WORKDIR)

    def execute(self, code: str) -> ExecutionResult:
        """
        在沙箱中执行 Python 代码。

        Args:
            code: Python 代码字符串

        Returns:
            ExecutionResult 对象
        """
        # 预检查：空代码
        if not code or not code.strip():
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Error: Empty code provided.",
                return_code=-1,
                error_type="ValueError",
            )

        return self.sandbox.execute(code)

    def cleanup(self):
        """清理沙箱资源"""
        self.sandbox.cleanup()
