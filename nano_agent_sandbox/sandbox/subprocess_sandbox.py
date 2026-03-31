"""
subprocess_sandbox.py — 子进程沙箱

通过 subprocess 在隔离的子进程中执行 Python 代码。
安全措施：
  1. 超时保护 — 防止死循环
  2. 输出截断 — 防止内存爆炸
  3. 独立工作目录 — 不污染主进程文件系统
  4. 环境变量隔离 — 不泄露 API Key 等敏感信息
"""
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nano_agent_sandbox.config import (
    SANDBOX_TIMEOUT,
    SANDBOX_MAX_OUTPUT,
    SANDBOX_WORKDIR,
)


@dataclass
class ExecutionResult:
    """代码执行结果"""
    success: bool           # 是否执行成功
    stdout: str             # 标准输出
    stderr: str             # 标准错误
    return_code: int        # 退出码
    timed_out: bool = False # 是否超时
    error_type: str = ""    # 错误分类（SyntaxError / ImportError / 等）

    @property
    def output(self) -> str:
        """合并输出，优先 stdout"""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr] {self.stderr}")
        if self.timed_out:
            parts.append(f"[TIMEOUT] Execution exceeded {SANDBOX_TIMEOUT}s limit.")
        return "\n".join(parts) if parts else "(no output)"

    def __str__(self):
        status = "✅ Success" if self.success else "❌ Failed"
        return f"{status}\n{self.output}"


class SubprocessSandbox:
    """基于子进程的轻量级代码沙箱"""

    def __init__(self, workdir: Optional[Path] = None):
        self.workdir = workdir or SANDBOX_WORKDIR
        self.workdir.mkdir(parents=True, exist_ok=True)

    def execute(self, code: str) -> ExecutionResult:
        """
        在隔离的子进程中执行 Python 代码。

        流程：
          1. 将代码写入临时 .py 文件
          2. 在子进程中执行（独立工作目录 + 干净环境）
          3. 捕获 stdout/stderr
          4. 超时自动 kill
          5. 分析错误类型
          6. 清理临时文件

        Args:
            code: 要执行的 Python 代码字符串

        Returns:
            ExecutionResult 对象
        """
        # 1) 写入临时文件
        tmp_file = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", dir=str(self.workdir),
                delete=False, encoding="utf-8",
            )
            tmp_file.write(code)
            tmp_file.flush()
            tmp_file.close()

            # 2) 构建安全的环境变量（隔离敏感信息）
            safe_env = self._build_safe_env()

            # 3) 执行
            try:
                proc = subprocess.run(
                    ["python3", tmp_file.name],
                    cwd=str(self.workdir),
                    env=safe_env,
                    capture_output=True,
                    text=True,
                    timeout=SANDBOX_TIMEOUT,
                )
                stdout = self._truncate(proc.stdout)
                stderr = self._truncate(proc.stderr)
                success = proc.returncode == 0
                error_type = self._classify_error(stderr) if not success else ""

                return ExecutionResult(
                    success=success,
                    stdout=stdout,
                    stderr=stderr,
                    return_code=proc.returncode,
                    error_type=error_type,
                )

            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timed out after {SANDBOX_TIMEOUT} seconds.",
                    return_code=-1,
                    timed_out=True,
                    error_type="TimeoutError",
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Sandbox error: {e}",
                return_code=-1,
                error_type="SandboxError",
            )
        finally:
            # 6) 清理临时文件
            if tmp_file and os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)

    def _build_safe_env(self) -> dict:
        """
        构建安全的环境变量，隔离敏感信息。
        只传递运行 Python 所必需的最小环境。
        """
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.workdir),
            "TMPDIR": str(self.workdir),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "PYTHONPATH": "",           # 不继承主进程的 PYTHONPATH
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    @staticmethod
    def _truncate(text: str) -> str:
        """截断过长输出"""
        if len(text) > SANDBOX_MAX_OUTPUT:
            return text[:SANDBOX_MAX_OUTPUT] + f"\n... (truncated, {len(text)} total chars)"
        return text

    @staticmethod
    def _classify_error(stderr: str) -> str:
        """从 stderr 中识别错误类型"""
        error_types = [
            "SyntaxError", "IndentationError", "TabError",
            "NameError", "TypeError", "ValueError", "AttributeError",
            "ImportError", "ModuleNotFoundError",
            "FileNotFoundError", "PermissionError", "OSError",
            "ZeroDivisionError", "IndexError", "KeyError",
            "RuntimeError", "RecursionError", "MemoryError",
        ]
        for et in error_types:
            if et in stderr:
                return et
        return "UnknownError"

    def cleanup(self):
        """清理沙箱工作目录中的临时产物"""
        import shutil
        if self.workdir.exists():
            for item in self.workdir.iterdir():
                if item.is_file() and item.suffix in (".py", ".pyc"):
                    item.unlink()
                elif item.is_dir() and item.name == "__pycache__":
                    shutil.rmtree(item)
