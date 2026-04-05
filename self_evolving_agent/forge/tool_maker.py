"""Tool Maker — uses LLM to generate tool code + schema + test cases.

This is the core innovation: when the agent lacks a tool, it writes one.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List

from ..registry.tool_store import ToolRecord


@dataclass
class ForgeResult:
    """Result of a tool forging attempt."""
    success: bool
    record: Optional[ToolRecord] = None
    error: str = ""


def parse_forge_response(llm_output: str) -> ForgeResult:
    """Parse LLM's tool generation response.

    Expected format from LLM:
    ```python
    def tool_name(arg1: str, arg2: int = 0) -> str:
        \"\"\"Description...\"\"\"
        ...
    ```

    ```json
    {
        "name": "tool_name",
        "description": "...",
        "parameters": { ... }
    }
    ```

    ```test
    {"arg1": "value1", "arg2": 42}
    ```
    """
    # Extract Python code block
    code_match = re.search(r"```python\s*\n(.*?)```", llm_output, re.DOTALL)
    if not code_match:
        return ForgeResult(success=False, error="No Python code block found in response")
    code = code_match.group(1).strip()

    # Extract function name from code
    func_match = re.search(r"def\s+(\w+)\s*\(", code)
    if not func_match:
        return ForgeResult(success=False, error="No function definition found in code")
    func_name = func_match.group(1)

    # Extract JSON schema block
    schema_match = re.search(r"```json\s*\n(.*?)```", llm_output, re.DOTALL)
    if schema_match:
        try:
            schema = json.loads(schema_match.group(1).strip())
        except json.JSONDecodeError as e:
            return ForgeResult(success=False, error=f"Invalid JSON schema: {e}")
    else:
        # Auto-generate a minimal schema from the function signature
        schema = _auto_schema(func_name, code)

    # Ensure schema has the right structure
    if "name" not in schema:
        schema["name"] = func_name
    if "description" not in schema:
        # Try to extract from docstring
        doc_match = re.search(r'"""(.*?)"""', code, re.DOTALL)
        schema["description"] = doc_match.group(1).strip() if doc_match else func_name

    # Extract test cases
    test_cases = []
    test_match = re.search(r"```test\s*\n(.*?)```", llm_output, re.DOTALL)
    if test_match:
        for line in test_match.group(1).strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    test_cases.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    record = ToolRecord(
        name=func_name,
        description=schema.get("description", ""),
        code=code,
        schema=schema,
        test_cases=test_cases,
        version=1,
        created_by="agent",
    )
    return ForgeResult(success=True, record=record)


def _auto_schema(func_name: str, code: str) -> dict:
    """Generate a minimal OpenAI function schema from function signature."""
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"name": func_name, "description": func_name, "parameters": {"type": "object", "properties": {}}}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            props = {}
            required = []
            defaults_offset = len(node.args.args) - len(node.args.defaults)
            for i, arg in enumerate(node.args.args):
                if arg.arg == "self":
                    continue
                annotation = "string"  # default
                if arg.annotation:
                    if isinstance(arg.annotation, ast.Name):
                        type_map = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
                        annotation = type_map.get(arg.annotation.id, "string")
                props[arg.arg] = {"type": annotation, "description": arg.arg}
                if i < defaults_offset:
                    required.append(arg.arg)

            doc = ast.get_docstring(node) or func_name
            return {
                "name": func_name,
                "description": doc,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            }

    return {"name": func_name, "description": func_name, "parameters": {"type": "object", "properties": {}}}
