#!/usr/bin/env python3
# OpenAI-compatible version of s01_agent_loop.py
# For Venus (v2.open.venus.oa.com) or other OpenAI-compatible providers.
"""
s01_agent_loop.py - The Agent Loop (OpenAI-compatible)

The entire secret of an AI coding agent in one pattern:

    while has_tool_calls:
        response = LLM(messages, tools)
        execute tools
        append results

    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> |  Tool   |
    |  prompt  |      |       |      | execute |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                          (loop continues)

This is the core loop: feed tool results back to the model
until the model decides to stop. Production agents layer
policy, hooks, and lifecycle controls on top.
"""
import json
import os
import subprocess

try:
    import readline
    readline.parse_and_bind('set bind-tty-special-chars off')
    readline.parse_and_bind('set input-meta on')
    readline.parse_and_bind('set output-meta on')
    readline.parse_and_bind('set convert-meta off')
    readline.parse_and_bind('set enable-meta-keybindings on')
except ImportError:
    pass

from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

WORKDIR = Path.cwd()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""


# -- TodoManager: LLM 用来管理自己任务进度的结构化状态 --
class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        """
        LLM 每次调用 todo 工具时，传入完整的任务列表（全量替换，非增量）。
        职责：校验 → 存储 → 渲染，返回可读的清单文本作为 tool_result 回传给 LLM。
        """
        # 防护：限制最多 20 条，避免 LLM 生成过长列表浪费 token
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed")

        validated = []          # 校验通过的任务列表
        in_progress_count = 0   # 统计 "正在进行" 的任务数

        for i, item in enumerate(items):
            # 提取字段，带默认值兜底（LLM 输出可能缺字段）
            text = str(item.get("text", "")).strip()
            status = str(item.get("status", "pending")).lower()
            item_id = str(item.get("id", str(i + 1)))  # 没传 id 就用序号

            # 校验：text 不能为空
            if not text:
                raise ValueError(f"Item {item_id}: text required")
            # 校验：status 必须是三种合法值之一
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {item_id}: invalid status '{status}'")

            if status == "in_progress":
                in_progress_count += 1
            validated.append({"id": item_id, "text": text, "status": status})

        # 核心约束：同一时刻只允许 1 个 in_progress，强制模型顺序聚焦
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")

        # 全量替换（不是 merge），每次 LLM 都传完整列表
        self.items = validated
        # 渲染成 [ ] / [>] / [x] 格式，作为 tool_result 返回给 LLM
        return self.render()

    def render(self) -> str:
        """渲染成可读的清单格式"""
        if not self.items:
            return "No todos."
        lines = []
        for item in self.items:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}[item["status"]]
            lines.append(f"{marker} #{item['id']}: {item['text']}")
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")
        return "\n".join(lines)


TODO = TodoManager()


def safe_path(p: str) -> Path:
    """确保路径不会逃出工作目录"""
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

# -- The dispatch map: {tool_name: handler} --
TOOL_HANDLERS = {
    ##  等价于 def bash(kw**): return run_bash(kw["command"])
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "todo":       lambda **kw: TODO.update(kw["items"]),  # 新增：todo 工具
}

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write content to file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Replace exact text in file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "todo", "description": "Update task list. Track progress on multi-step tasks.",
     "parameters": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "text": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["id", "text", "status"]}}}, "required": ["items"]}}},
]
def run_bash(command: str)->str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try :
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        # strip() 是 Python 字符串方法，作用是去除字符串首尾的空白字符（空格、换行符 \n、制表符 \t 等）
        out = (r.stdout + r.stderr).strip() 
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"  

def run_read(path: str, limit: int = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    # Build OpenAI-format messages
    oai_messages = [{"role": "system", "content": SYSTEM}]
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], str):
            oai_messages.append({"role": "user", "content": m["content"]})

    rounds_since_todo = 0  # 记录距离上次调用 todo 工具过了几轮
    while True:
        response = client.chat.completions.create(
            model=MODEL, messages=oai_messages,
            tools=TOOLS, max_tokens=8000,
        )
        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg})
        oai_messages.append(msg)

        # If the model didn't call a tool, we're done
        if not msg.tool_calls:
            if msg.content:
                print(msg.content)
            return

        # Execute each tool call, collect results
        used_todo = False  # 本轮是否用了 todo 工具
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            handler = TOOL_HANDLERS.get(tc.function.name)
            try:
                output = handler(**args) if handler else f"Unknown tool: {tc.function.name}"
            except Exception as e:
                output = f"Error: {e}"
            print(f"\033[33m> {tc.function.name}({args})\033[0m")
            print(str(output)[:200])
            oai_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(output),
            })
            if tc.function.name == "todo":
                used_todo = True

        # Nag reminder: 连续 3 轮没更新 todo，注入提醒
        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1
        if rounds_since_todo >= 3:
            oai_messages.append({"role": "user", "content": "<reminder>Update your todos.</reminder>"})

if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in (":q", "/exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        print()

