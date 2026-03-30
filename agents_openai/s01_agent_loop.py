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

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}]


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    # Build OpenAI-format messages
    oai_messages = [{"role": "system", "content": SYSTEM}]
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], str):
            oai_messages.append({"role": "user", "content": m["content"]})

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
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"\033[33m$ {args['command']}\033[0m")
            output = run_bash(args["command"])
            print(output[:200])
            oai_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output,
            })


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        # Print final response
        last = history[-1]["content"]
        if hasattr(last, "content") and last.content:
            pass  # already printed in agent_loop
        print()
