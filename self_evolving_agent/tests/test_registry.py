"""Tests for the Tool Registry and Tool Store."""

import pytest
import tempfile
from pathlib import Path

from self_evolving_agent.registry.tool_store import ToolStore, ToolRecord
from self_evolving_agent.registry.tool_registry import ToolRegistry


@pytest.fixture
def tmp_store(tmp_path):
    return ToolStore(store_dir=tmp_path / "tools")


@pytest.fixture
def sample_record():
    return ToolRecord(
        name="greet",
        description="Generate a greeting",
        code='def greet(name: str) -> str:\n    """Greet someone."""\n    return f"Hello, {name}!"',
        schema={
            "name": "greet",
            "description": "Generate a greeting",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
        test_cases=[{"name": "World"}],
    )


class TestToolStore:
    def test_save_and_load(self, tmp_store, sample_record):
        tmp_store.save(sample_record)
        loaded = tmp_store.load("greet")
        assert loaded is not None
        assert loaded.name == "greet"
        assert loaded.code == sample_record.code

    def test_load_nonexistent(self, tmp_store):
        assert tmp_store.load("nonexistent") is None

    def test_load_all(self, tmp_store, sample_record):
        tmp_store.save(sample_record)
        records = tmp_store.load_all()
        assert len(records) == 1
        assert records[0].name == "greet"

    def test_delete(self, tmp_store, sample_record):
        tmp_store.save(sample_record)
        assert tmp_store.exists("greet")
        tmp_store.delete("greet")
        assert not tmp_store.exists("greet")


class TestToolRegistry:
    def test_builtin_tools_loaded(self, tmp_store):
        registry = ToolRegistry(store=tmp_store)
        assert registry.has_tool("run_python")
        assert registry.has_tool("read_file")
        assert registry.has_tool("write_file")

    def test_register_agent_tool(self, tmp_store, sample_record):
        registry = ToolRegistry(store=tmp_store)
        initial = registry.total_tool_count
        registry.register(sample_record)
        assert registry.total_tool_count == initial + 1
        assert registry.has_tool("greet")
        assert registry.agent_tool_count == 1

    def test_dispatch_builtin(self, tmp_store):
        registry = ToolRegistry(store=tmp_store)
        result = registry.dispatch("list_files", {})
        assert isinstance(result, str)

    def test_dispatch_unknown_tool(self, tmp_store):
        registry = ToolRegistry(store=tmp_store)
        result = registry.dispatch("nonexistent_tool", {})
        assert "Unknown tool" in result

    def test_unregister_agent_tool(self, tmp_store, sample_record):
        registry = ToolRegistry(store=tmp_store)
        registry.register(sample_record)
        assert registry.has_tool("greet")
        registry.unregister("greet")
        assert not registry.has_tool("greet")

    def test_cannot_unregister_builtin(self, tmp_store):
        registry = ToolRegistry(store=tmp_store)
        result = registry.unregister("run_python")
        assert result is False
        assert registry.has_tool("run_python")

    def test_search_tools(self, tmp_store, sample_record):
        registry = ToolRegistry(store=tmp_store)
        registry.register(sample_record)
        results = registry.search_tools("greet")
        assert len(results) >= 1

    def test_persistence_across_instances(self, tmp_store, sample_record):
        reg1 = ToolRegistry(store=tmp_store)
        reg1.register(sample_record)
        # New registry instance should load persisted tools
        reg2 = ToolRegistry(store=tmp_store)
        assert reg2.has_tool("greet")
        assert reg2.agent_tool_count == 1
