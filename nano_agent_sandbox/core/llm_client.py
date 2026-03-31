"""
llm_client.py — LLM 统一接口

职责：
  1. 封装 OpenAI 兼容 API 的调用细节
  2. 解析 LLM 输出：工具调用 / 代码块 / 纯文本
  3. 流式与非流式对话支持
"""
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Generator, List, Optional, Tuple

from openai import OpenAI

from nano_agent_sandbox.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS


# ── 数据结构 ────────────────────────────────────────

@dataclass
class ToolCall:
    """一次工具调用"""
    id: str
    name: str
    arguments: dict


@dataclass
class Action:
    """LLM 单次输出解析后的结构化动作"""
    text: Optional[str] = None         # 纯文本回复
    tool_calls: List[ToolCall] = field(default_factory=list)  # 工具调用列表
    code_blocks: List[str] = field(default_factory=list)      # 提取的可执行代码块

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def has_code(self) -> bool:
        return len(self.code_blocks) > 0

    @property
    def is_final(self) -> bool:
        """没有工具调用也没有需要执行的代码 → 最终回复"""
        return not self.has_tool_calls and not self.has_code


# ── LLM Client ──────────────────────────────────────

class LLMClient:
    """OpenAI 兼容的 LLM 客户端"""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL
        self.max_tokens = LLM_MAX_TOKENS

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None) -> "Action":
        """
        发送消息列表给 LLM，返回解析后的 Action。

        Args:
            messages: OpenAI 格式的消息列表
            tools:    OpenAI 格式的工具定义列表（可选）

        Returns:
            Action 对象，包含文本 / 工具调用 / 代码块
        """
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
        )
        if tools:
            kwargs["tools"] = tools

        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        return self.parse_action(msg)

    def chat_stream(
        self,
        messages: List[dict],
        tools: Optional[List[dict]] = None,
    ) -> Tuple[str, "Action"]:
        """
        流式调用 LLM，实时打印文本 token，最终返回完整 Action。

        Returns:
            (full_text, Action) 元组
        """
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            stream=True,
        )
        if tools:
            kwargs["tools"] = tools

        stream = self.client.chat.completions.create(**kwargs)

        full_text = ""
        # tool_calls 累积: {index: {id, name, arguments_str}}
        tc_map = {}  # type: dict

        for chunk in stream:
            delta = chunk.choices[0].delta

            # ── 文本增量 ──
            if delta.content:
                sys.stdout.write(delta.content)
                sys.stdout.flush()
                full_text += delta.content

            # ── 工具调用增量 ──
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tc_map:
                        tc_map[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tc_map[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_map[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_map[idx]["arguments"] += tc_delta.function.arguments

        # 如果有文本输出，补一个换行
        if full_text:
            sys.stdout.write("\n")
            sys.stdout.flush()

        # 构建 Action
        action = Action(text=full_text if full_text else None)

        # 解析工具调用
        if tc_map:
            for idx in sorted(tc_map.keys()):
                tc_info = tc_map[idx]
                try:
                    args = json.loads(tc_info["arguments"])
                except json.JSONDecodeError:
                    args = {"raw": tc_info["arguments"]}
                action.tool_calls.append(ToolCall(
                    id=tc_info["id"],
                    name=tc_info["name"],
                    arguments=args,
                ))

        # 从文本中提取代码块（CodeAct 降级）
        if full_text and not action.has_tool_calls:
            code_pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)
            blocks = code_pattern.findall(full_text)
            action.code_blocks = [b.strip() for b in blocks if b.strip()]

        return full_text, action

    def parse_action(self, message) -> Action:
        """
        解析 LLM 返回的 message 为结构化 Action。

        解析优先级：
          1. 如果有 tool_calls → 提取为 ToolCall 列表
          2. 如果文本中有 ```python 代码块 → 提取为可执行代码
          3. 否则 → 纯文本回复
        """
        action = Action(text=message.content)

        # 1) 解析工具调用
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                action.tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        # 2) 从文本中提取 python 代码块（CodeAct 模式的降级方案）
        if message.content and not action.has_tool_calls:
            code_pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)
            blocks = code_pattern.findall(message.content)
            action.code_blocks = [b.strip() for b in blocks if b.strip()]

        return action

    @property
    def raw_message(self):
        """暴露底层 message 对象，方便 agent_loop 追加到历史"""
        return self._last_message
