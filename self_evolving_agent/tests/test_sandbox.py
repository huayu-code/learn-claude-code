"""Tests for the code sandbox (executor + security)."""

import pytest
from self_evolving_agent.sandbox.executor import execute_code, execute_function
from self_evolving_agent.sandbox.security import validate_code


class TestSecurity:
    def test_safe_code_passes(self):
        result = validate_code("import json\nx = json.dumps({'a': 1})")
        assert result.safe

    def test_blocks_os_import(self):
        result = validate_code("import os\nos.system('ls')")
        assert not result.safe
        assert any("os" in v for v in result.violations)

    def test_blocks_subprocess(self):
        result = validate_code("import subprocess\nsubprocess.run(['ls'])")
        assert not result.safe

    def test_blocks_eval(self):
        result = validate_code("x = eval('1+1')")
        assert not result.safe

    def test_blocks_exec(self):
        result = validate_code("exec('print(1)')")
        assert not result.safe

    def test_blocks_dunder_import(self):
        result = validate_code("m = __import__('os')")
        assert not result.safe

    def test_allows_safe_modules(self):
        result = validate_code("import json\nimport math\nimport re\nimport datetime")
        assert result.safe

    def test_syntax_error(self):
        result = validate_code("def broken(:\n  pass")
        assert not result.safe
        assert any("SyntaxError" in v for v in result.violations)


class TestExecutor:
    def test_basic_execution(self):
        result = execute_code("print('hello world')")
        assert result.success
        assert "hello world" in result.stdout

    def test_error_handling(self):
        result = execute_code("raise ValueError('test error')")
        assert not result.success
        assert "ValueError" in result.stderr

    def test_timeout(self):
        result = execute_code("import time; time.sleep(100)", timeout=2)
        assert not result.success
        assert result.timed_out

    def test_no_api_key_leak(self):
        result = execute_code("""\
import os
key = os.environ.get('OPENAI_API_KEY', 'NOT_FOUND')
print(f'key={key}')
""")
        # The sandbox env should not have OPENAI_API_KEY
        assert "NOT_FOUND" in result.stdout or not result.success

    def test_execute_function(self):
        code = '''
def add(a: int, b: int) -> str:
    return str(a + b)
'''
        result = execute_function(code, "add", {"a": 3, "b": 4})
        assert result.success
        assert result.return_value == "7"
