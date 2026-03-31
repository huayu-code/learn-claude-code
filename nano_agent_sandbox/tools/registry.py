"""
registry.py — 工具注册中心 (Dispatch Map 模式)

职责：
  1. 注册工具：name → handler 映射
  2. 分发调用：根据 tool name 路由到对应 handler
  3. 返回工具 schema 列表：供 LLM 使用
"""
from typing import Callable, Dict, List, Optional

from nano_agent_sandbox.tools.tool_schema import TOOL_SCHEMAS


class ToolRegistry:
    """
    工具注册中心。

    设计思路（Dispatch Map 模式）：
      - 注册时建立 {name: handler} 的映射表
      - 调用时根据 name 查表，传入参数执行
      - 与 learn-claude-code 的 TOOL_HANDLERS dict 一脉相承，但增加了动态注册能力
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._schemas: List[dict] = []

    def register(self, name: str, handler: Callable, schema: Optional[dict] = None):
        """
        注册一个工具。

        Args:
            name:    工具名称（与 schema 中的 function.name 一致）
            handler: 处理函数，接收 **kwargs，返回 str
            schema:  OpenAI 格式的工具 schema（可选，如果不传则从全局 schema 中查找）
        """
        self._handlers[name] = handler
        if schema:
            self._schemas.append(schema)

    def dispatch(self, name: str, arguments: dict) -> str:
        """
        分发工具调用。

        Args:
            name:      工具名称
            arguments: 参数字典

        Returns:
            工具执行结果字符串
        """
        handler = self._handlers.get(name)
        if not handler:
            return f"Error: Unknown tool '{name}'. Available: {list(self._handlers.keys())}"
        try:
            result = handler(**arguments)
            return str(result)
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    def list_tools(self) -> List[dict]:
        """返回所有已注册工具的 OpenAI schema，供 LLM chat 使用"""
        if self._schemas:
            return self._schemas
        # fallback：从全局 TOOL_SCHEMAS 中筛选已注册的工具
        return [
            s for s in TOOL_SCHEMAS
            if s.get("function", {}).get("name") in self._handlers
               or s.get("function", s).get("name") in self._handlers
        ]

    @property
    def tool_names(self) -> List[str]:
        return list(self._handlers.keys())
