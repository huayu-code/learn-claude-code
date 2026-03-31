"""
test_agent_loop.py — Agent Loop 单测

验证上下文管理、工具注册等核心流程（不依赖真实 LLM）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nano_agent_sandbox.core.context_manager import ContextManager
from nano_agent_sandbox.tools.registry import ToolRegistry
from nano_agent_sandbox.tools.builtin.todo_tool import TodoManager


def test_context_append():
    ctx = ContextManager("You are a test agent.")
    ctx.append_user("hello")
    ctx.append_assistant({"role": "assistant", "content": "hi there"})
    msgs = ctx.get_messages()
    assert len(msgs) == 3  # system + user + assistant
    assert msgs[0]["role"] == "system"
    assert msgs[1]["content"] == "hello"
    print("✅ test_context_append")


def test_context_observation():
    ctx = ContextManager("test")
    ctx.inject_observation("update your todos")
    msgs = ctx.get_messages()
    assert "<observation>" in msgs[1]["content"]
    print("✅ test_context_observation")


def test_tool_registry():
    reg = ToolRegistry()
    reg.register("echo", lambda text: f"echo: {text}")
    result = reg.dispatch("echo", {"text": "hello"})
    assert result == "echo: hello"
    print("✅ test_tool_registry")


def test_tool_dispatch_unknown():
    reg = ToolRegistry()
    result = reg.dispatch("nonexistent", {})
    assert "Unknown tool" in result
    print("✅ test_tool_dispatch_unknown")


def test_todo_manager():
    tm = TodoManager()
    result = tm.update([
        {"id": "1", "text": "task A", "status": "completed"},
        {"id": "2", "text": "task B", "status": "in_progress"},
        {"id": "3", "text": "task C", "status": "pending"},
    ])
    assert "[x]" in result
    assert "[>]" in result
    assert "[ ]" in result
    assert "1/3 completed" in result
    print("✅ test_todo_manager")


def test_todo_rejects_multiple_in_progress():
    tm = TodoManager()
    try:
        tm.update([
            {"id": "1", "text": "A", "status": "in_progress"},
            {"id": "2", "text": "B", "status": "in_progress"},
        ])
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Only one" in str(e)
    print("✅ test_todo_rejects_multiple_in_progress")


if __name__ == "__main__":
    test_context_append()
    test_context_observation()
    test_tool_registry()
    test_tool_dispatch_unknown()
    test_todo_manager()
    test_todo_rejects_multiple_in_progress()
    print("\n🎉 All agent loop tests passed!")
