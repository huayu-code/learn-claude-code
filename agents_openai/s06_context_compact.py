#!/usr/bin/env python3
# OpenAI-compatible version of s06_context_compact.py
"""
s06_context_compact.py - Compact (OpenAI-compatible)

Three-layer compression pipeline so the agent can work forever:
  Layer 1: micro_compact (silent, every turn)
  Layer 2: auto_compact (when tokens > threshold)
  Layer 3: compact tool (manual trigger)

Key insight: "The agent can forget strategically and keep working forever."
"""

import json
import os
import subprocess
import time
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

WORKDIR = Path.cwd()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks."

THRESHOLD = 50000
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
KEEP_RECENT = 3


def estimate_tokens(oai_messages: list) -> int:
    return len(json.dumps(oai_messages, default=str)) // 4


def micro_compact(oai_messages: list):
    """Layer 1: replace old tool results with placeholders."""
    tool_indices = []
    for i, msg in enumerate(oai_messages):
        if isinstance(msg, dict) and msg.get("role") == "tool":
            tool_indices.append(i)
    if len(tool_indices) <= KEEP_RECENT:
        return
    for idx in tool_indices[:-KEEP_RECENT]:
        msg = oai_messages[idx]
        if isinstance(msg.get("content"), str) and len(msg["content"]) > 100:
            msg["content"] = "[Previous tool result cleared]"


def auto_compact(oai_messages: list) -> list:
    """Layer 2: save transcript, summarize, replace messages."""
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as f:
        for msg in oai_messages:
            f.write(json.dumps(msg, default=str) + "\n")
    print(f"[transcript saved: {transcript_path}]")

    conv_text = json.dumps(oai_messages, default=str)[-80000:]
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content":
            "Summarize this conversation for continuity. Include: "
            "1) What was accomplished, 2) Current state, 3) Key decisions made. "
            "Be concise but preserve critical details.\n\n" + conv_text}],
        max_tokens=2000,
    )
    summary = response.choices[0].message.content
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
    ]


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
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


TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "compact":    lambda **kw: "Manual compression requested.",
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
    {"type": "function", "function": {"name": "compact", "description": "Trigger manual conversation compression.",
     "parameters": {"type": "object", "properties": {"focus": {"type": "string", "description": "What to preserve in the summary"}}}}},
]


def agent_loop(messages: list):
    oai_messages = [{"role": "system", "content": SYSTEM}]
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], str):
            oai_messages.append({"role": "user", "content": m["content"]})

    while True:
        micro_compact(oai_messages)
        if estimate_tokens(oai_messages) > THRESHOLD:
            print("[auto_compact triggered]")
            oai_messages[:] = auto_compact(oai_messages)

        response = client.chat.completions.create(
            model=MODEL, messages=oai_messages, tools=TOOLS, max_tokens=8000,
        )
        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg})
        oai_messages.append(msg)

        if not msg.tool_calls:
            if msg.content:
                print(msg.content)
            return

        manual_compact = False
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            if tc.function.name == "compact":
                manual_compact = True
                output = "Compressing..."
            else:
                handler = TOOL_HANDLERS.get(tc.function.name)
                try:
                    output = handler(**args) if handler else f"Unknown tool: {tc.function.name}"
                except Exception as e:
                    output = f"Error: {e}"
            print(f"> {tc.function.name}:")
            print(str(output)[:200])
            oai_messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(output)})

        if manual_compact:
            print("[manual compact]")
            oai_messages[:] = auto_compact(oai_messages)
            return


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms06 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        print()
