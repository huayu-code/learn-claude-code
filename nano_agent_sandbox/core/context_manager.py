"""
context_manager.py — 上下文管理

职责：
  1. 维护 OpenAI 格式的消息历史
  2. 上下文超长时自动压缩（摘要替换旧消息）
  3. 注入执行结果（observation）到上下文
"""
from typing import List

from nano_agent_sandbox.config import CONTEXT_MAX_TOKENS, COMPACT_KEEP_RECENT


class ContextManager:
    """管理 Agent 的对话上下文窗口"""

    def __init__(self, system_prompt: str):
        # system 消息始终在最前面，不会被压缩掉
        self.system_message = {"role": "system", "content": system_prompt}
        self.messages: List[dict] = []  # 不含 system，纯对话历史

    def get_messages(self) -> List[dict]:
        """返回完整的消息列表（system + 历史），供 LLM 调用"""
        return [self.system_message] + self.messages

    def append_user(self, content: str):
        """追加用户消息"""
        self.messages.append({"role": "user", "content": content})

    def append_assistant(self, message):
        """追加 assistant 原始 message（保留 tool_calls 等元信息）"""
        self.messages.append(message)

    def append_tool_result(self, tool_call_id: str, content: str):
        """追加单条工具执行结果"""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def inject_observation(self, observation: str):
        """
        注入一条系统观察（如 nag reminder、自愈提示等）。
        以 user 角色注入，因为 OpenAI API 中 tool_result 必须跟在 tool_call 后面。
        """
        self.messages.append({
            "role": "user",
            "content": f"<observation>{observation}</observation>",
        })

    # ── 上下文压缩 ──────────────────────────────────

    def _estimate_tokens(self) -> int:
        """粗估当前消息的 token 数（1 字符 ≈ 1 token，中文约 2 token/字）"""
        total = 0
        for msg in self.messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                for part in content:
                    total += len(str(part))
        return total

    def compact_if_needed(self, llm_client=None) -> bool:
        """
        上下文超过软上限时，压缩旧消息为摘要。

        策略：保留最近 COMPACT_KEEP_RECENT 条消息，将之前的消息压缩成一段摘要。
        如果没有传入 llm_client，使用简单截断；如果传入了，用 LLM 做摘要。

        Returns:
            是否执行了压缩
        """
        if self._estimate_tokens() < CONTEXT_MAX_TOKENS:
            return False

        if len(self.messages) <= COMPACT_KEEP_RECENT:
            return False

        old_messages = self.messages[:-COMPACT_KEEP_RECENT]
        recent_messages = self.messages[-COMPACT_KEEP_RECENT:]

        if llm_client:
            # 用 LLM 生成摘要
            summary = self._llm_summarize(old_messages, llm_client)
        else:
            # 简单截断：提取关键信息
            summary = self._simple_summarize(old_messages)

        # 用摘要替换旧消息
        self.messages = [
            {"role": "user", "content": f"<context_summary>{summary}</context_summary>"},
        ] + recent_messages
        return True

    def _simple_summarize(self, messages: List[dict]) -> str:
        """简单摘要：提取 assistant 文本和工具调用名"""
        parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "assistant" and isinstance(content, str) and content:
                # 截取前 200 字符
                parts.append(f"Assistant: {content[:200]}...")
            elif role == "tool":
                parts.append(f"Tool result: {str(content)[:100]}...")
        if not parts:
            return "Previous conversation context (compressed)."
        return "\n".join(parts[-10:])  # 最多保留最近 10 条摘要

    def _llm_summarize(self, messages: List[dict], llm_client) -> str:
        """用 LLM 对旧消息做摘要"""
        text_parts = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                text_parts.append(f"[{msg['role']}] {content[:500]}")
        history_text = "\n".join(text_parts[-20:])

        summary_messages = [
            {"role": "system", "content": "Summarize the following conversation history in 3-5 bullet points. Focus on: what tasks were attempted, what succeeded/failed, and current state."},
            {"role": "user", "content": history_text},
        ]
        action = llm_client.chat(summary_messages)
        return action.text or "Context compressed."
