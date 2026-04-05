"""LLM Client — streaming OpenAI-compatible API wrapper with Tool Calling support."""

import sys
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from openai import OpenAI

from .. import config


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Action:
    """Parsed LLM response: text reply and/or tool calls."""
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)

    @property
    def is_final(self) -> bool:
        """True if this is a text-only response (no tool calls)."""
        return len(self.tool_calls) == 0


class LLMClient:
    """Streaming LLM client with tool calling support."""

    def __init__(self):
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
        )
        self.model = config.LLM_MODEL

    def chat(
        self,
        messages: List[dict],
        tools: Optional[List[dict]] = None,
        stream: bool = True,
    ) -> Action:
        """Send messages to LLM and return parsed Action."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if not stream:
            return self._sync_call(kwargs)
        return self._stream_call(kwargs)

    def _sync_call(self, kwargs: dict) -> Action:
        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        action = Action(text=msg.content or "")
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                action.tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        return action

    def _stream_call(self, kwargs: dict) -> Action:
        """Stream response, printing text in real-time, collecting tool calls."""
        stream = self.client.chat.completions.create(**kwargs)

        text_parts = []
        # tool_call accumulators: index -> {id, name, arguments_str}
        tc_accum: Dict[int, dict] = {}

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Text content
            if delta.content:
                sys.stdout.write(delta.content)
                sys.stdout.flush()
                text_parts.append(delta.content)

            # Tool calls (streamed as deltas)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tc_accum:
                        tc_accum[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tc_accum[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_accum[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_accum[idx]["arguments"] += tc_delta.function.arguments

        # Finalize
        action = Action(text="".join(text_parts))
        for idx in sorted(tc_accum):
            acc = tc_accum[idx]
            try:
                args = json.loads(acc["arguments"])
            except json.JSONDecodeError:
                args = {}
            action.tool_calls.append(ToolCall(
                id=acc["id"],
                name=acc["name"],
                arguments=args,
            ))

        if text_parts:
            print()  # newline after streaming

        return action

    def simple_chat(self, messages: List[dict]) -> str:
        """Simple non-streaming call, returns text only (for forge/evolve prompts)."""
        action = self.chat(messages, tools=None, stream=False)
        return action.text
