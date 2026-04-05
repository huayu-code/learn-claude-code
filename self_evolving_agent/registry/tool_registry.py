"""Dynamic Tool Registry — manages both built-in and agent-created tools.

Supports hot-loading: new tools are usable immediately after registration
without restart. Persists agent-created tools via ToolStore.
"""

import json
from typing import Dict, List, Callable, Optional

from .tool_store import ToolStore, ToolRecord
from .builtin_tools import BUILTIN_SCHEMAS, BUILTIN_HANDLERS
from ..sandbox.executor import execute_function


class ToolRegistry:
    """Central registry for all tools (built-in + agent-created)."""

    def __init__(self, store: Optional[ToolStore] = None):
        self.store = store or ToolStore()
        # name -> handler function
        self._handlers: Dict[str, Callable] = dict(BUILTIN_HANDLERS)
        # name -> OpenAI function schema
        self._schemas: Dict[str, dict] = {
            s["function"]["name"]: s for s in BUILTIN_SCHEMAS
        }
        # name -> ToolRecord (agent-created only)
        self._agent_tools: Dict[str, ToolRecord] = {}
        # Load persisted agent tools
        self._load_persisted()

    def _load_persisted(self) -> None:
        """Load all agent-created tools from disk."""
        for record in self.store.load_all():
            self._register_agent_tool(record)

    def _register_agent_tool(self, record: ToolRecord) -> None:
        """Register an agent-created tool (code-based, executed in sandbox)."""
        self._agent_tools[record.name] = record
        self._schemas[record.name] = {
            "type": "function",
            "function": record.schema,
        }
        # Create a handler that executes the tool code in sandbox
        func_code = record.code
        func_name = record.name

        def handler(args: dict, _code=func_code, _name=func_name) -> str:
            result = execute_function(_code, _name, args)
            if result.success:
                return result.return_value or result.stdout.strip() or "✅ Done (no output)"
            return f"❌ Tool execution failed:\n{result.stderr}"

        self._handlers[record.name] = handler

    def register(self, record: ToolRecord, persist: bool = True) -> None:
        """Register a new agent-created tool. Immediately available for use."""
        self._register_agent_tool(record)
        if persist:
            self.store.save(record)

    def unregister(self, name: str) -> bool:
        """Remove an agent-created tool."""
        if name in BUILTIN_HANDLERS:
            return False  # cannot remove built-in tools
        removed = False
        if name in self._agent_tools:
            del self._agent_tools[name]
            removed = True
        self._handlers.pop(name, None)
        self._schemas.pop(name, None)
        self.store.delete(name)
        return removed

    def get_schemas(self) -> List[dict]:
        """Get all tool schemas for OpenAI API."""
        return list(self._schemas.values())

    def dispatch(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool by name with given arguments."""
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"❌ Unknown tool: '{tool_name}'. Use list_tools to see available tools."
        try:
            return handler(arguments)
        except Exception as e:
            return f"❌ Tool error ({tool_name}): {type(e).__name__}: {e}"

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    def list_tools(self) -> str:
        """Human-readable list of all tools."""
        lines = ["📦 Available Tools:\n"]
        lines.append("── Built-in ──")
        for name in BUILTIN_HANDLERS:
            schema = self._schemas[name]["function"]
            lines.append(f"  🔧 {name}: {schema.get('description', '')[:80]}")
        if self._agent_tools:
            lines.append("\n── Agent-Created ──")
            for name, record in self._agent_tools.items():
                lines.append(f"  🛠️  {name} (v{record.version}): {record.description[:80]}")
        else:
            lines.append("\n── Agent-Created ──")
            lines.append("  (none yet — the agent will create tools as needed)")
        return "\n".join(lines)

    def search_tools(self, query: str) -> List[str]:
        """Simple keyword search across tool names and descriptions."""
        query_lower = query.lower()
        matches = []
        for name, schema in self._schemas.items():
            desc = schema["function"].get("description", "")
            if query_lower in name.lower() or query_lower in desc.lower():
                matches.append(f"{name}: {desc[:100]}")
        return matches

    @property
    def agent_tool_count(self) -> int:
        return len(self._agent_tools)

    @property
    def total_tool_count(self) -> int:
        return len(self._handlers)
