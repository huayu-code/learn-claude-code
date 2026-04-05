"""Tests for the Tool Forge (maker + validator + tester)."""

import pytest

from self_evolving_agent.forge.tool_maker import parse_forge_response
from self_evolving_agent.forge.sandbox_tester import run_tool_tests
from self_evolving_agent.registry.tool_store import ToolRecord


class TestToolMaker:
    def test_parse_valid_response(self):
        llm_output = '''Here's a tool:

```python
def add_numbers(a: int, b: int) -> str:
    """Add two numbers and return the result."""
    return str(a + b)
```

```json
{
    "name": "add_numbers",
    "description": "Add two numbers",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {"type": "integer", "description": "First number"},
            "b": {"type": "integer", "description": "Second number"}
        },
        "required": ["a", "b"]
    }
}
```

```test
{"a": 1, "b": 2}
{"a": -5, "b": 5}
```
'''
        result = parse_forge_response(llm_output)
        assert result.success
        assert result.record.name == "add_numbers"
        assert len(result.record.test_cases) == 2

    def test_parse_no_code_block(self):
        result = parse_forge_response("Just some text without code")
        assert not result.success
        assert "No Python code block" in result.error

    def test_parse_auto_schema(self):
        llm_output = '''
```python
def multiply(x: int, y: int) -> str:
    """Multiply two numbers."""
    return str(x * y)
```
'''
        result = parse_forge_response(llm_output)
        assert result.success
        assert result.record.name == "multiply"
        # Schema should be auto-generated
        assert "parameters" in result.record.schema


class TestSandboxTester:
    def test_passing_tool(self):
        record = ToolRecord(
            name="hello",
            description="Say hello",
            code='def hello(name: str) -> str:\n    return f"Hello, {name}!"',
            schema={},
            test_cases=[{"name": "World"}],
        )
        passed, messages = run_tool_tests(record)
        assert passed
        assert any("passed" in m for m in messages)

    def test_failing_tool(self):
        record = ToolRecord(
            name="broken",
            description="Broken tool",
            code='def broken(x: str) -> str:\n    raise ValueError("always fails")',
            schema={},
            test_cases=[{"x": "test"}],
        )
        passed, messages = run_tool_tests(record)
        assert not passed
        assert any("failed" in m.lower() for m in messages)

    def test_smoke_test_no_cases(self):
        record = ToolRecord(
            name="simple",
            description="Simple tool",
            code='def simple() -> str:\n    return "ok"',
            schema={},
            test_cases=[],
        )
        passed, messages = run_tool_tests(record)
        assert passed
        assert any("Smoke test" in m for m in messages)
