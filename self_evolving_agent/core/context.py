"""Context Manager — message history management with automatic compression."""

from typing import List

from .. import config


class ContextManager:
    """Manages the conversation message list with auto-compression."""

    def __init__(self, system_prompt: str):
        self._system_msg = {"role": "system", "content": system_prompt}
        self._messages: List[dict] = []

    @property
    def messages(self) -> List[dict]:
        return [self._system_msg] + self._messages

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        if content:
            self._messages.append({"role": "assistant", "content": content})

    def add_assistant_tool_calls(self, tool_calls: list) -> None:
        """Add assistant message with tool_calls (for multi-turn tool calling)."""
        self._messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": __import__("json").dumps(tc.arguments, ensure_ascii=False),
                    }
                }
                for tc in tool_calls
            ],
        })

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def check_compress(self) -> bool:
        """Compress old messages if context is too long. Returns True if compressed."""
        total = sum(len(str(m.get("content", ""))) for m in self._messages)
        if total <= config.CONTEXT_COMPRESS_THRESHOLD:
            return False

        # Keep the most recent 6 messages, summarize the rest
        keep = 6
        if len(self._messages) <= keep:
            return False

        old = self._messages[:-keep]
        summary_parts = []
        for m in old:
            role = m.get("role", "?")
            content = str(m.get("content", ""))[:200]
            if content:
                summary_parts.append(f"[{role}] {content}")

        summary = "Previous conversation summary:\n" + "\n".join(summary_parts[-10:])
        self._messages = [
            {"role": "user", "content": summary}
        ] + self._messages[-keep:]
        return True

    @property
    def turn_count(self) -> int:
        return len([m for m in self._messages if m["role"] == "user"])
