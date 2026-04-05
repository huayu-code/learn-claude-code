"""Sandbox Tester — validates generated tool code by running test cases in sandbox."""

from typing import List, Tuple

from ..sandbox.executor import execute_function, ExecutionResult
from ..registry.tool_store import ToolRecord
from .. import config


def run_tool_tests(record: ToolRecord) -> Tuple[bool, List[str]]:
    """Run all test cases for a tool in the sandbox.

    Returns (all_passed, messages).
    """
    messages = []

    if not record.test_cases:
        # No test cases — do a basic smoke test (just check it loads without error)
        smoke_result = _smoke_test(record)
        if smoke_result.success:
            messages.append("✅ Smoke test passed (no test cases provided)")
            return True, messages
        else:
            messages.append(f"❌ Smoke test failed: {smoke_result.stderr}")
            return False, messages

    all_passed = True
    for i, test_input in enumerate(record.test_cases, 1):
        result = execute_function(
            record.code,
            record.name,
            test_input,
            timeout=config.TOOL_TEST_TIMEOUT,
        )
        if result.success:
            ret = result.return_value or result.stdout.strip() or "(no output)"
            messages.append(f"✅ Test {i} passed — input: {test_input} → {ret[:200]}")
        else:
            all_passed = False
            err = result.stderr[:300]
            messages.append(f"❌ Test {i} failed — input: {test_input}\n   Error: {err}")

    return all_passed, messages


def _smoke_test(record: ToolRecord) -> ExecutionResult:
    """Basic check: can the function definition be loaded without errors."""
    from ..sandbox.executor import execute_code

    smoke_code = f"""\
{record.code}

# Just verify the function is callable
assert callable({record.name}), "Function is not callable"
print("smoke_test_ok")
"""
    return execute_code(smoke_code, timeout=5)
