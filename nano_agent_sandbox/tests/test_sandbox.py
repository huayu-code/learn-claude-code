"""
test_sandbox.py — 沙箱安全性测试

验证：
  1. 正常代码执行
  2. 超时保护
  3. 语法错误捕获
  4. 环境变量隔离
  5. 输出截断
"""
import os
import sys
from pathlib import Path

# 确保可以导入 nano_agent_sandbox
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nano_agent_sandbox.sandbox.subprocess_sandbox import SubprocessSandbox


def test_basic_execution():
    """正常代码应该成功执行"""
    sandbox = SubprocessSandbox()
    result = sandbox.execute("print('hello world')")
    assert result.success, f"Expected success, got: {result}"
    assert "hello world" in result.stdout
    print("✅ test_basic_execution")


def test_math_computation():
    """数学计算应该正常返回"""
    sandbox = SubprocessSandbox()
    result = sandbox.execute("print(sum(range(100)))")
    assert result.success
    assert "4950" in result.stdout
    print("✅ test_math_computation")


def test_syntax_error():
    """语法错误应该被捕获"""
    sandbox = SubprocessSandbox()
    result = sandbox.execute("def foo(:\n  pass")
    assert not result.success
    assert result.error_type == "SyntaxError"
    print("✅ test_syntax_error")


def test_import_error():
    """导入不存在的模块应该返回 ImportError"""
    sandbox = SubprocessSandbox()
    result = sandbox.execute("import nonexistent_module_xyz")
    assert not result.success
    assert result.error_type in ("ImportError", "ModuleNotFoundError")
    print("✅ test_import_error")


def test_timeout():
    """死循环应该被超时终止"""
    sandbox = SubprocessSandbox()
    # 用一个短超时的沙箱测试
    from nano_agent_sandbox.sandbox import subprocess_sandbox
    original = subprocess_sandbox.SANDBOX_TIMEOUT
    subprocess_sandbox.SANDBOX_TIMEOUT = 3  # 3秒超时
    try:
        result = sandbox.execute("import time; time.sleep(10)")
        assert not result.success
        assert result.timed_out
        print("✅ test_timeout")
    finally:
        subprocess_sandbox.SANDBOX_TIMEOUT = original


def test_env_isolation():
    """沙箱不应该泄露主进程的环境变量"""
    os.environ["SECRET_KEY_FOR_TEST"] = "super_secret_123"
    sandbox = SubprocessSandbox()
    result = sandbox.execute("""
import os
val = os.environ.get('SECRET_KEY_FOR_TEST', 'NOT_FOUND')
print(val)
""")
    assert result.success
    assert "NOT_FOUND" in result.stdout, f"Env leaked! Got: {result.stdout}"
    del os.environ["SECRET_KEY_FOR_TEST"]
    print("✅ test_env_isolation")


def test_multiline_output():
    """多行输出应该完整捕获"""
    sandbox = SubprocessSandbox()
    result = sandbox.execute("for i in range(5): print(f'line {i}')")
    assert result.success
    assert "line 4" in result.stdout
    print("✅ test_multiline_output")


if __name__ == "__main__":
    test_basic_execution()
    test_math_computation()
    test_syntax_error()
    test_import_error()
    test_timeout()
    test_env_isolation()
    test_multiline_output()
    print("\n🎉 All sandbox tests passed!")
