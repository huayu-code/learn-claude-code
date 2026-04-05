"""Global configuration for Self-Evolving Agent."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("MODEL_ID", "gpt-4o")

# ── Agent Loop ───────────────────────────────────────────────────
MAX_AGENT_TURNS = 20
CONTEXT_COMPRESS_THRESHOLD = 60_000  # chars

# ── Sandbox ──────────────────────────────────────────────────────
SANDBOX_DIR = Path("/tmp/self-evolving-sandbox")
SANDBOX_TIMEOUT = 15  # seconds
SANDBOX_MAX_OUTPUT = 30_000  # chars

# ── Tool Forge ───────────────────────────────────────────────────
MAX_FIX_ATTEMPTS = 3  # max self-repair rounds
TOOL_TEST_TIMEOUT = 10  # seconds per test

# ── Tool Registry ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
TOOL_STORE_DIR = PROJECT_ROOT / "tool_store"

# ── Security ─────────────────────────────────────────────────────
BLOCKED_MODULES = {
    "os", "subprocess", "shutil", "sys", "ctypes",
    "importlib", "code", "codeop", "compileall",
    "signal", "socket", "http", "ftplib", "smtplib",
    "webbrowser", "antigravity",
}
ALLOWED_MODULES = {
    "json", "csv", "math", "re", "datetime", "collections",
    "itertools", "functools", "operator", "string", "textwrap",
    "hashlib", "base64", "uuid", "pathlib", "typing",
    "dataclasses", "enum", "copy", "pprint", "statistics",
    # data / viz (installed in sandbox)
    "pandas", "numpy", "matplotlib", "openpyxl", "xlsxwriter",
    "requests", "bs4", "PIL", "markdown", "yaml", "toml",
}
BLOCKED_BUILTINS = {"eval", "exec", "compile", "__import__", "globals", "locals"}
