"""Built-in tools that ship with the agent out of the box."""

import json
from pathlib import Path
from typing import Dict, Any

from ..sandbox.executor import execute_code, ExecutionResult
from .. import config


def run_python(code: str) -> str:
    """Execute arbitrary Python code in the sandbox and return output."""
    result = execute_code(code)
    return result.summary()


def read_file(path: str) -> str:
    """Read a file from the sandbox directory."""
    sandbox = config.SANDBOX_DIR
    target = (sandbox / path).resolve()
    if not str(target).startswith(str(sandbox.resolve())):
        return f"❌ Access denied: path must be inside {sandbox}"
    if not target.exists():
        return f"❌ File not found: {path}"
    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > 10_000:
        content = content[:10_000] + "\n... (truncated)"
    return content


def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandbox directory."""
    sandbox = config.SANDBOX_DIR
    target = (sandbox / path).resolve()
    if not str(target).startswith(str(sandbox.resolve())):
        return f"❌ Access denied: path must be inside {sandbox}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"✅ Written {len(content)} chars to {path}"


def list_files(directory: str = ".") -> str:
    """List files in the sandbox directory."""
    sandbox = config.SANDBOX_DIR
    target = (sandbox / directory).resolve()
    if not str(target).startswith(str(sandbox.resolve())):
        return f"❌ Access denied: path must be inside {sandbox}"
    if not target.exists():
        return f"❌ Directory not found: {directory}"
    entries = []
    for p in sorted(target.iterdir()):
        prefix = "📁" if p.is_dir() else "📄"
        size = f" ({p.stat().st_size} bytes)" if p.is_file() else ""
        entries.append(f"{prefix} {p.name}{size}")
    return "\n".join(entries) if entries else "(empty directory)"


def install_package(package: str) -> str:
    """Install a pip package in the sandbox environment."""
    code = f"""
import subprocess, sys
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "--quiet", "{package}"],
    capture_output=True, text=True, timeout=60
)
if result.returncode == 0:
    print(f"✅ Installed {{'{package}'}}")
else:
    print(f"❌ Failed: {{result.stderr[:500]}}")
"""
    result = execute_code(code, timeout=60)
    return result.stdout.strip() or result.stderr.strip()


# ── Schema definitions for OpenAI Tool Calling ───────────────────

BUILTIN_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python code in a secure sandbox. Use for computation, data processing, file operations within the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the sandbox working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path within sandbox"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the sandbox working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path within sandbox"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Relative directory path (default: current)", "default": "."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Install a Python package via pip in the sandbox. Use when you need a library that's not available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package": {"type": "string", "description": "Package name (e.g. 'pandas', 'matplotlib')"}
                },
                "required": ["package"],
            },
        },
    },
]

BUILTIN_HANDLERS = {
    "run_python": lambda args: run_python(args["code"]),
    "read_file": lambda args: read_file(args["path"]),
    "write_file": lambda args: write_file(args["path"], args["content"]),
    "list_files": lambda args: list_files(args.get("directory", ".")),
    "install_package": lambda args: install_package(args["package"]),
}
