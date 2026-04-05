"""Agent Loop — ReAct + Tool-Making decision engine.

The core loop:
1. Think: LLM reasons about the task
2. Act: If tool exists → call it; if not → enter Tool Forge
3. Observe: Feed result back to LLM
4. Repeat until LLM gives a final text response
"""

import sys
import json
from typing import Optional, List

from .llm_client import LLMClient, Action, ToolCall
from .context import ContextManager
from ..registry.tool_registry import ToolRegistry
from ..forge.tool_maker import parse_forge_response
from ..forge.code_validator import validate_code
from ..forge.sandbox_tester import run_tool_tests
from ..forge.tool_evolver import build_fix_prompt
from .. import config


# Special meta-tool schemas (not in registry, handled by agent loop)
_META_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_tool",
            "description": (
                "Create a new reusable tool when no existing tool can accomplish the task. "
                "Describe what the tool should do, its inputs and outputs. "
                "The system will generate, test, and register the tool automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_description": {
                        "type": "string",
                        "description": "Detailed description of what the tool should do, its inputs, outputs, and any libraries needed",
                    },
                    "suggested_name": {
                        "type": "string",
                        "description": "Suggested function name (snake_case)",
                    },
                },
                "required": ["tool_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_all_tools",
            "description": "List all available tools (built-in and agent-created).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class AgentLoop:
    """Main agent loop with self-evolving tool creation capability."""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        context: ContextManager,
    ):
        self.llm = llm
        self.registry = registry
        self.context = context
        self._experiment_log: List[dict] = []

    def run(self, user_input: str) -> str:
        """Process user input through the ReAct loop."""
        self.context.add_user(user_input)
        final_text = ""

        for turn in range(1, config.MAX_AGENT_TURNS + 1):
            # ── Think ────────────────────────────────────────────
            tools = self.registry.get_schemas() + _META_TOOL_SCHEMAS
            print(f"\n{'─'*60}")
            print(f"🧠 Turn {turn}/{config.MAX_AGENT_TURNS}")
            print(f"{'─'*60}")

            action = self.llm.chat(self.context.messages, tools=tools)

            # ── Final response (no tool calls) ───────────────────
            if action.is_final:
                self.context.add_assistant(action.text)
                final_text = action.text
                break

            # ── Act: process tool calls ──────────────────────────
            self.context.add_assistant_tool_calls(action.tool_calls)

            for tc in action.tool_calls:
                result = self._handle_tool_call(tc)
                self.context.add_tool_result(tc.id, result)
                self._experiment_log.append({
                    "turn": turn,
                    "tool": tc.name,
                    "args": tc.arguments,
                    "result_preview": result[:200],
                })

            # ── Observe: compress if needed ──────────────────────
            if self.context.check_compress():
                print("📦 Context compressed")

        else:
            final_text = "(max turns reached)"

        return final_text

    def _handle_tool_call(self, tc: ToolCall) -> str:
        """Route tool call to registry or meta-tool handler."""
        print(f"\n🔧 Tool: {tc.name}")
        if tc.arguments:
            preview = json.dumps(tc.arguments, ensure_ascii=False)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            print(f"   Args: {preview}")

        # Meta tools
        if tc.name == "create_tool":
            result = self._forge_tool(
                tc.arguments.get("tool_description", ""),
                tc.arguments.get("suggested_name"),
            )
        elif tc.name == "list_all_tools":
            result = self.registry.list_tools()
        else:
            # Regular tool dispatch
            result = self.registry.dispatch(tc.name, tc.arguments)

        print(f"   Result: {result[:200]}{'...' if len(result)>200 else ''}")
        return result

    def _forge_tool(self, description: str, suggested_name: Optional[str] = None) -> str:
        """The Tool Forge pipeline: generate → validate → test → register."""
        print(f"\n🔨 FORGE: Creating new tool...")
        print(f"   Description: {description[:100]}")

        # Step 1: Ask LLM to generate tool code
        forge_prompt = self._build_forge_prompt(description, suggested_name)
        forge_messages = [
            {"role": "system", "content": "You are an expert Python developer. Generate clean, safe, well-tested tool code."},
            {"role": "user", "content": forge_prompt},
        ]

        for attempt in range(1, config.MAX_FIX_ATTEMPTS + 1):
            print(f"\n   📝 Generation attempt {attempt}/{config.MAX_FIX_ATTEMPTS}")

            response_text = self.llm.simple_chat(forge_messages)
            forge_result = parse_forge_response(response_text)

            if not forge_result.success:
                print(f"   ❌ Parse failed: {forge_result.error}")
                if attempt < config.MAX_FIX_ATTEMPTS:
                    forge_messages.append({"role": "assistant", "content": response_text})
                    forge_messages.append({"role": "user", "content": f"Error: {forge_result.error}. Please fix and try again."})
                    continue
                return f"❌ Failed to generate tool after {attempt} attempts: {forge_result.error}"

            record = forge_result.record

            # Step 2: Security validation
            print(f"   🔒 Security check...")
            validation = validate_code(record.code)
            if not validation.safe:
                print(f"   {validation}")
                if attempt < config.MAX_FIX_ATTEMPTS:
                    fix_prompt = build_fix_prompt(record.code, validation.violations, attempt)
                    forge_messages.append({"role": "assistant", "content": response_text})
                    forge_messages.append({"role": "user", "content": fix_prompt})
                    continue
                return f"❌ Tool code failed security validation:\n{validation}"
            print(f"   ✅ Security check passed")

            # Step 3: Sandbox testing
            print(f"   🧪 Running tests in sandbox...")
            passed, test_messages = run_tool_tests(record)
            for msg in test_messages:
                print(f"   {msg}")

            if not passed:
                if attempt < config.MAX_FIX_ATTEMPTS:
                    fix_prompt = build_fix_prompt(record.code, test_messages, attempt)
                    forge_messages.append({"role": "assistant", "content": response_text})
                    forge_messages.append({"role": "user", "content": fix_prompt})
                    continue
                return f"❌ Tool failed testing after {attempt} attempts"

            # Step 4: Register!
            print(f"   ✅ All tests passed — registering '{record.name}'")
            self.registry.register(record)

            return (
                f"✅ New tool '{record.name}' created and registered!\n"
                f"Description: {record.description}\n"
                f"Parameters: {json.dumps(record.schema.get('parameters', {}), indent=2)}\n"
                f"You can now use it directly."
            )

        return "❌ Tool creation failed after all attempts"

    def _build_forge_prompt(self, description: str, suggested_name: Optional[str]) -> str:
        name_hint = f"\nSuggested function name: `{suggested_name}`" if suggested_name else ""
        existing = ", ".join(
            s["function"]["name"] for s in self.registry.get_schemas()
        )
        return f"""\
Create a Python tool function based on this description:

{description}{name_hint}

## Already existing tools (do NOT duplicate):
{existing}

## Rules:
1. Write a single function with type hints and docstring
2. Function must return a string (the result)
3. Only use safe imports (json, csv, math, re, datetime, pandas, numpy, matplotlib, requests, etc.)
4. Do NOT use: os, subprocess, shutil, eval, exec, __import__
5. All file operations must use paths relative to the current directory
6. Handle errors gracefully with try/except

## Output format:

```python
def function_name(param1: str, param2: int = 0) -> str:
    \"\"\"Brief description of what the tool does.\"\"\"
    # implementation
    return "result"
```

```json
{{
    "name": "function_name",
    "description": "Brief description",
    "parameters": {{
        "type": "object",
        "properties": {{
            "param1": {{"type": "string", "description": "..."}},
            "param2": {{"type": "integer", "description": "...", "default": 0}}
        }},
        "required": ["param1"]
    }}
}}
```

```test
{{"param1": "test_value", "param2": 42}}
{{"param1": "another_test"}}
```
"""

    @property
    def experiment_log(self) -> List[dict]:
        return self._experiment_log
