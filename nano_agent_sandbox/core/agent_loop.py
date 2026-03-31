"""
agent_loop.py — Agent 主循环 (ReAct Loop)

    ┌─────────┐    ┌─────────┐    ┌──────────┐
    │ Observe  │───▶│  Think  │───▶│   Act    │
    │(收集状态)│    │(LLM推理) │    │(执行动作) │
    └─────────┘    └─────────┘    └────┬─────┘
         ▲                              │
         │         ┌──────────┐         │
         └─────────│ Reflect  │◀────────┘
                   │(检查结果) │
                   └──────────┘

职责：
  1. observe()  — 收集用户输入 + 环境状态
  2. think()    — 调用 LLM 决策下一步
  3. act()      — 分发到工具执行或沙箱代码执行
  4. reflect()  — 检查结果，决定继续/结束/触发自愈
"""
import json
from typing import List, Tuple

from nano_agent_sandbox.config import MAX_AGENT_TURNS
from nano_agent_sandbox.core.llm_client import LLMClient, Action
from nano_agent_sandbox.core.context_manager import ContextManager
from nano_agent_sandbox.tools.registry import ToolRegistry
from nano_agent_sandbox.self_heal.error_analyzer import ErrorAnalyzer
from nano_agent_sandbox.self_heal.retry_strategy import RetryStrategy


class AgentLoop:
    """ReAct Agent 主循环"""

    def __init__(
        self,
        llm: LLMClient,
        context: ContextManager,
        tools: ToolRegistry,
        error_analyzer: ErrorAnalyzer,
        retry_strategy: RetryStrategy,
    ):
        self.llm = llm
        self.context = context
        self.tools = tools
        self.error_analyzer = error_analyzer
        self.retry_strategy = retry_strategy

    def run(self, user_input: str) -> str:
        """
        接收用户输入，运行 ReAct 循环直到获得最终回复。
        LLM 文本输出通过流式实时打印到终端。

        Returns:
            Agent 的最终文本回复
        """
        # ── Observe: 收集用户输入 ──
        self.context.append_user(user_input)

        final_text = ""
        for turn in range(MAX_AGENT_TURNS):
            # ── Think: 调用 LLM（流式输出文本）──
            streamed_text, action = self._think_stream()

            # ── Act: 执行动作 ──
            if action.is_final:
                # LLM 给出了最终回复，已经流式打印过了
                final_text = streamed_text
                break

            results = self._act(action)

            # ── Reflect: 检查结果，决定下一步 ──
            should_continue = self._reflect(results)
            if not should_continue:
                final_text = streamed_text or (results[-1] if results else "")
                break

            # 上下文压缩检查
            self.context.compact_if_needed(self.llm)
        else:
            final_text = "(Agent reached maximum turns limit.)"
            self.context.inject_observation(
                "Maximum turns reached. Please summarize progress and stop."
            )

        return final_text

    def _think_stream(self):
        """调用 LLM 流式推理，实时打印文本，返回 (streamed_text, Action)"""
        messages = self.context.get_messages()
        tool_schemas = self.tools.list_tools()
        streamed_text, action = self.llm.chat_stream(
            messages, tools=tool_schemas if tool_schemas else None
        )

        # 把 assistant 原始 message 追加到上下文
        assistant_msg = {"role": "assistant", "content": action.text or ""}
        if action.has_tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in action.tool_calls
            ]
        self.context.append_assistant(assistant_msg)

        return streamed_text, action

    def _act(self, action: Action) -> List[str]:
        """
        执行 Action 中的工具调用或代码块。

        Returns:
            执行结果列表
        """
        results = []

        # 1) 优先处理工具调用（标准 function calling 路径）
        if action.has_tool_calls:
            for tc in action.tool_calls:
                output = self.tools.dispatch(tc.name, tc.arguments)
                print(f"\033[33m> {tc.name}({tc.arguments})\033[0m")
                print(str(output)[:300])
                self.context.append_tool_result(tc.id, str(output))
                results.append(str(output))

        # 2) 文本中的代码块 → 走 run_code 工具（CodeAct 降级路径）
        elif action.has_code:
            for code in action.code_blocks:
                output = self.tools.dispatch("run_code", {"code": code})
                print(f"\033[33m> run_code (from text)\033[0m")
                print(str(output)[:300])
                self.context.inject_observation(f"Code execution result:\n{output}")
                results.append(str(output))

        return results

    def _reflect(self, results: List[str]) -> bool:
        """
        检查执行结果，决定是否继续循环。
        如果有错误且可重试，触发自愈流程。

        Returns:
            True = 继续循环，False = 停止
        """
        if not results:
            return True  # 没有结果，继续让 LLM 决定

        for result in results:
            if self._is_error(result):
                # 分析错误
                error_info = self.error_analyzer.classify_error(result)
                suggestion = self.error_analyzer.suggest_fix(error_info)

                # 判断是否重试
                if self.retry_strategy.should_retry(error_info):
                    self.retry_strategy.record_attempt(error_info)
                    # 注入自愈提示到上下文
                    self.context.inject_observation(
                        f"<self_heal>\n"
                        f"Error type: {error_info['type']}\n"
                        f"Suggestion: {suggestion}\n"
                        f"Retries left: {self.retry_strategy.retries_left(error_info)}\n"
                        f"Please fix and retry.\n"
                        f"</self_heal>"
                    )
                    return True  # 继续循环，让 LLM 自愈

        return True  # 默认继续

    @staticmethod
    def _is_error(result: str) -> bool:
        """简单判断执行结果是否包含错误"""
        error_indicators = [
            "Error:", "Traceback", "Exception", "SyntaxError",
            "NameError", "TypeError", "ImportError", "FileNotFoundError",
            "TimeoutError", "MemoryError",
        ]
        return any(indicator in result for indicator in error_indicators)
