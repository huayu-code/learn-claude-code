"""Process-isolated code executor (sandbox).

Each execution runs in a separate subprocess with:
- Cleaned environment variables (no API keys leaked)
- Timeout protection
- Working directory isolation under /tmp/self-evolving-sandbox/
- Output truncation
"""

import subprocess
import textwrap
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import config


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    return_value: Optional[str] = None
    timed_out: bool = False

    def summary(self, max_len: int = 2000) -> str:
        parts = []
        if self.timed_out:
            parts.append(f"⏰ Timed out after {config.SANDBOX_TIMEOUT}s")
        if self.stdout.strip():
            out = self.stdout[:max_len]
            parts.append(f"stdout:\n{out}")
        if self.stderr.strip():
            err = self.stderr[:max_len]
            parts.append(f"stderr:\n{err}")
        if self.return_value:
            parts.append(f"return: {self.return_value[:max_len]}")
        if not parts:
            parts.append("(no output)")
        status = "✅ Success" if self.success else "❌ Failed"
        return f"{status}\n" + "\n".join(parts)


def _ensure_sandbox_dir() -> Path:
    config.SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    return config.SANDBOX_DIR


def _safe_env() -> dict:
    """Build a minimal environment — never leak API keys."""
    import os
    env = {}
    for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    env["PYTHONPATH"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def execute_code(code: str, timeout: Optional[int] = None) -> ExecutionResult:
    """Execute Python code string in a subprocess sandbox."""
    sandbox_dir = _ensure_sandbox_dir()
    timeout = timeout or config.SANDBOX_TIMEOUT

    wrapper = textwrap.dedent(f"""\
        import sys, json, io
        sys.path.insert(0, '{sandbox_dir}')

        _result = None
        try:
            exec(compile('''{{}}''', '<sandbox>', 'exec'))
        except Exception as _e:
            print(f"Error: {{type(_e).__name__}}: {{_e}}", file=sys.stderr)
            sys.exit(1)
    """)

    # Write code to a temp file to avoid shell escaping issues
    code_file = sandbox_dir / "_exec_code.py"
    # Build a proper wrapper that executes the user code
    indented = textwrap.indent(code, "    ")
    full_code = (
        "import sys, json\n"
        "\n"
        "try:\n"
        f"{indented}\n"
        "except Exception as _e:\n"
        '    print(f"Error: {type(_e).__name__}: {_e}", file=sys.stderr)\n'
        "    sys.exit(1)\n"
    )

    code_file.write_text(full_code, encoding="utf-8")

    try:
        proc = subprocess.run(
            [sys.executable, str(code_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(sandbox_dir),
            env=_safe_env(),
        )
        stdout = proc.stdout[:config.SANDBOX_MAX_OUTPUT]
        stderr = proc.stderr[:config.SANDBOX_MAX_OUTPUT]
        return ExecutionResult(
            success=proc.returncode == 0,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Execution timed out after {timeout}s",
            timed_out=True,
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Sandbox error: {type(e).__name__}: {e}",
        )
    finally:
        if code_file.exists():
            code_file.unlink()


import sys


def execute_function(
    func_code: str,
    func_name: str,
    args: dict,
    timeout: Optional[int] = None,
) -> ExecutionResult:
    """Execute a function defined in func_code with given args, return its result."""
    call_args = json.dumps(args, ensure_ascii=False)
    test_code = textwrap.dedent(f"""\
import json

{func_code}

_args = json.loads('''{call_args}''')
_result = {func_name}(**_args)
print(json.dumps({{"__return__": str(_result)}}, ensure_ascii=False))
""")
    result = execute_code(test_code, timeout=timeout)
    # Try to extract return value from stdout
    if result.success and result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            try:
                parsed = json.loads(line)
                if "__return__" in parsed:
                    result.return_value = parsed["__return__"]
                    break
            except (json.JSONDecodeError, KeyError):
                continue
    return result
