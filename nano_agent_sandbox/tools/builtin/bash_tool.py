"""
bash_tool.py — Shell 命令工具

与 learn-claude-code 一致，提供 bash 命令执行能力。
包含危险命令拦截。
"""
import subprocess

from nano_agent_sandbox.config import SANDBOX_TIMEOUT, SANDBOX_MAX_OUTPUT, WORKDIR

# 黑名单命令
DANGEROUS_PATTERNS = [
    "rm -rf /", "sudo", "shutdown", "reboot",
    "> /dev/", "mkfs", "dd if=", ":(){",
]


def bash(command: str) -> str:
    """
    执行 shell 命令并返回结果。

    安全措施：
      - 危险命令黑名单拦截
      - 超时保护
      - 输出截断
    """
    if any(d in command for d in DANGEROUS_PATTERNS):
        return "Error: Dangerous command blocked."
    try:
        r = subprocess.run(
            command, shell=True, cwd=str(WORKDIR),
            capture_output=True, text=True,
            timeout=SANDBOX_TIMEOUT,
        )
        out = (r.stdout + r.stderr).strip()
        if len(out) > SANDBOX_MAX_OUTPUT:
            out = out[:SANDBOX_MAX_OUTPUT] + "\n... (truncated)"
        return out if out else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Timeout ({SANDBOX_TIMEOUT}s)"
    except Exception as e:
        return f"Error: {e}"
