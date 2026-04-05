"""CLI entry point for Self-Evolving Agent.

Composition Root: assembles all components and starts the REPL.
"""

import sys
import argparse

from .core.llm_client import LLMClient
from .core.context import ContextManager
from .core.agent_loop import AgentLoop
from .registry.tool_registry import ToolRegistry
from .registry.tool_store import ToolStore
from .prompts.system_prompt import build_system_prompt
from . import config


BANNER = r"""
╔═══════════════════════════════════════════════════════╗
║          🧬  Self-Evolving Agent  🧬                  ║
║                                                       ║
║   An AI agent that creates its own tools on the fly   ║
║   Inspired by LATM & Voyager                          ║
╚═══════════════════════════════════════════════════════╝
"""


def build_agent() -> AgentLoop:
    """Assemble all components (Composition Root pattern)."""
    # 1. Tool Store + Registry
    store = ToolStore()
    registry = ToolRegistry(store=store)

    # 2. System prompt
    prompt = build_system_prompt(
        tool_count=registry.total_tool_count,
        agent_tool_count=registry.agent_tool_count,
    )

    # 3. Context
    context = ContextManager(system_prompt=prompt)

    # 4. LLM Client
    llm = LLMClient()

    # 5. Agent Loop
    return AgentLoop(llm=llm, registry=registry, context=context)


def print_status(agent: AgentLoop) -> None:
    """Print current agent status."""
    reg = agent.registry
    print(f"\n📊 Status: {reg.total_tool_count} tools ({reg.agent_tool_count} agent-created)")
    print(f"   Model: {config.LLM_MODEL}")
    print(f"   Sandbox: {config.SANDBOX_DIR}")
    print(f"   Tool Store: {config.TOOL_STORE_DIR}\n")


def interactive_mode(agent: AgentLoop) -> None:
    """Run the agent in interactive REPL mode."""
    print(BANNER)
    print_status(agent)
    print("Commands: 'tools' (list tools), 'log' (experiment log), 'q' (quit)\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye! 👋")
            break

        if not user_input:
            continue
        if user_input.lower() in ("q", "quit", "exit"):
            print("Bye! 👋")
            break
        if user_input.lower() == "tools":
            print(agent.registry.list_tools())
            continue
        if user_input.lower() == "log":
            if not agent.experiment_log:
                print("(no tool calls yet)")
            else:
                for entry in agent.experiment_log[-10:]:
                    print(f"  Turn {entry['turn']}: {entry['tool']}({json.dumps(entry['args'], ensure_ascii=False)[:80]})")
            continue
        if user_input.lower() == "status":
            print_status(agent)
            continue

        # Run the agent
        print()
        response = agent.run(user_input)
        print(f"\n{'═'*60}")
        print(f"📋 Final Answer:\n{response}")
        print(f"{'═'*60}\n")


def single_task_mode(agent: AgentLoop, task: str) -> None:
    """Run a single task and exit."""
    print(f"🎯 Task: {task}\n")
    response = agent.run(task)
    print(f"\n{'═'*60}")
    print(f"📋 Result:\n{response}")
    print(f"{'═'*60}")


def main():
    parser = argparse.ArgumentParser(description="Self-Evolving Agent")
    parser.add_argument("--task", "-t", help="Single task to execute (non-interactive)")
    args = parser.parse_args()

    if not config.LLM_API_KEY:
        print("❌ Please set OPENAI_API_KEY in your .env file or environment")
        sys.exit(1)

    agent = build_agent()

    if args.task:
        single_task_mode(agent, args.task)
    else:
        interactive_mode(agent)


import json

if __name__ == "__main__":
    main()
