"""
config.py — 全局配置，集中管理所有可调参数
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# ── LLM ────────────────────────────────────────────
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
LLM_MODEL = os.getenv("MODEL_ID", "gpt-4o")
LLM_MAX_TOKENS = 4096

# ── 沙箱 ───────────────────────────────────────────
SANDBOX_TIMEOUT = 30          # 单次代码执行超时(秒)
SANDBOX_MAX_MEMORY_MB = 512   # 内存上限(MB)
SANDBOX_MAX_OUTPUT = 50_000   # 输出截断长度(字符)

# ── Agent Loop ─────────────────────────────────────
MAX_AGENT_TURNS = 25          # 单次任务最大循环轮次
MAX_RETRIES = 3               # 自愈最大重试次数
CONTEXT_MAX_TOKENS = 60_000   # 上下文窗口软上限(字符数，粗估)
COMPACT_KEEP_RECENT = 6       # 压缩时保留最近 N 条消息

# ── 工作区 ─────────────────────────────────────────
WORKDIR = Path.cwd()
SANDBOX_WORKDIR = Path("/tmp/nano-sandbox-work")
