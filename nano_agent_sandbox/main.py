#!/usr/bin/env python3
"""
nano-agent-sandbox — 从零构建带安全沙箱的 Code Execution Agent

入口 CLI：初始化所有组件，启动交互式 Agent 循环。

架构五层：
  Agent Loop (ReAct) → LLM Client → Tool Registry → Sandbox → Self-Heal
"""
import sys
from pathlib import Path

# 让 nano_agent_sandbox 包可以被导入（从项目子目录运行时）
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nano_agent_sandbox.config import SANDBOX_WORKDIR
from nano_agent_sandbox.core.llm_client import LLMClient
from nano_agent_sandbox.core.context_manager import ContextManager
from nano_agent_sandbox.core.agent_loop import AgentLoop
from nano_agent_sandbox.sandbox.executor import CodeExecutor
from nano_agent_sandbox.sandbox.file_manager import FileManager
from nano_agent_sandbox.tools.registry import ToolRegistry
from nano_agent_sandbox.tools.tool_schema import TOOL_SCHEMAS
from nano_agent_sandbox.tools.builtin import run_code, read_file, write_file
from nano_agent_sandbox.tools.builtin.bash_tool import bash
from nano_agent_sandbox.tools.builtin.todo_tool import todo
from nano_agent_sandbox.self_heal.error_analyzer import ErrorAnalyzer
from nano_agent_sandbox.self_heal.retry_strategy import RetryStrategy
from nano_agent_sandbox.prompts.system_prompt import build_system_prompt


def build_agent() -> AgentLoop:
    """组装所有组件，返回 AgentLoop 实例"""

    # 1) 沙箱层
    executor = CodeExecutor(workdir=SANDBOX_WORKDIR)
    file_mgr = FileManager(workdir=SANDBOX_WORKDIR)

    # 2) 初始化工具的依赖注入
    run_code.init(executor)
    read_file.init(file_mgr)
    write_file.init(file_mgr)

    # 3) 工具注册
    registry = ToolRegistry()
    for schema in TOOL_SCHEMAS:
        name = schema["function"]["name"]
        handler_map = {
            "run_code": run_code.run_code,
            "read_file": read_file.read_file,
            "write_file": write_file.write_file,
            "bash": bash,
            "todo": todo,
        }
        if name in handler_map:
            registry.register(name, handler_map[name], schema)

    # 4) LLM + 上下文
    llm = LLMClient()
    context = ContextManager(system_prompt=build_system_prompt())

    # 5) 自愈
    error_analyzer = ErrorAnalyzer()
    retry_strategy = RetryStrategy()

    # 6) 组装 Agent Loop
    return AgentLoop(
        llm=llm,
        context=context,
        tools=registry,
        error_analyzer=error_analyzer,
        retry_strategy=retry_strategy,
    )


def main():
    """交互式 CLI 入口"""
    print("=" * 60)
    print("  nano-agent-sandbox")
    print("  Code Execution Agent with Secure Sandbox")
    print("=" * 60)
    print(f"  Sandbox dir: {SANDBOX_WORKDIR}")
    print("  Type your task, or 'q' to quit.\n")

    agent = build_agent()

    while True:
        try:
            query = input("\033[36mnano >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if query.strip().lower() in ("q", "exit", "quit", ""):
            print("Bye!")
            break

        # 每次新任务重置自愈计数器
        agent.retry_strategy.reset()

        # 运行 Agent（LLM 文本已通过流式实时打印）
        response = agent.run(query)

        # 流式输出已在 LLM 推理时实时打印，这里仅打印分隔
        print()

        # 检查并展示产物
        from nano_agent_sandbox.sandbox.file_manager import FileManager
        fm = FileManager(workdir=SANDBOX_WORKDIR)
        artifacts = fm.collect_artifacts()
        if artifacts:
            print("\033[33m📎 Artifacts:\033[0m")
            for a in artifacts:
                print(f"  - {a['name']} ({a['size']} bytes): {a['path']}")
            print()


if __name__ == "__main__":
    main()
