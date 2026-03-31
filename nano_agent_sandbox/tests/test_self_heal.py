"""
test_self_heal.py — 自愈机制测试

验证：
  1. 错误分类准确
  2. 修复建议针对性
  3. 重试策略：次数限制、死循环防护
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nano_agent_sandbox.self_heal.error_analyzer import ErrorAnalyzer
from nano_agent_sandbox.self_heal.retry_strategy import RetryStrategy


def test_classify_syntax_error():
    analyzer = ErrorAnalyzer()
    info = analyzer.classify_error(
        'File "test.py", line 5\n    def foo(:\nSyntaxError: invalid syntax'
    )
    assert info["type"] == "syntax"
    assert info["error_name"] == "SyntaxError"
    assert info["line_number"] == 5
    print("✅ test_classify_syntax_error")


def test_classify_import_error():
    analyzer = ErrorAnalyzer()
    info = analyzer.classify_error(
        "ModuleNotFoundError: No module named 'pandas'"
    )
    assert info["type"] == "import"
    assert info["error_name"] == "ModuleNotFoundError"
    print("✅ test_classify_import_error")


def test_classify_timeout():
    analyzer = ErrorAnalyzer()
    info = analyzer.classify_error("TimeoutError: Execution timed out after 30s")
    assert info["type"] == "timeout"
    print("✅ test_classify_timeout")


def test_suggest_fix_has_content():
    analyzer = ErrorAnalyzer()
    info = analyzer.classify_error("ImportError: No module named 'numpy'")
    suggestion = analyzer.suggest_fix(info)
    assert "pip install" in suggestion
    print("✅ test_suggest_fix_has_content")


def test_retry_respects_max():
    strategy = RetryStrategy(max_retries=2)
    error = {"type": "runtime", "error_name": "TypeError", "message": "test"}
    assert strategy.should_retry(error)
    strategy.record_attempt(error)
    assert strategy.should_retry(error)
    strategy.record_attempt(error)
    assert not strategy.should_retry(error)  # 已耗尽
    print("✅ test_retry_respects_max")


def test_retry_rejects_resource_error():
    strategy = RetryStrategy()
    error = {"type": "resource", "error_name": "MemoryError", "message": "OOM"}
    assert not strategy.should_retry(error)
    print("✅ test_retry_rejects_resource_error")


def test_retry_reset():
    strategy = RetryStrategy(max_retries=1)
    error = {"type": "syntax", "error_name": "SyntaxError", "message": "bad"}
    strategy.record_attempt(error)
    assert not strategy.should_retry(error)
    strategy.reset()
    assert strategy.should_retry(error)  # 重置后又可以了
    print("✅ test_retry_reset")


if __name__ == "__main__":
    test_classify_syntax_error()
    test_classify_import_error()
    test_classify_timeout()
    test_suggest_fix_has_content()
    test_retry_respects_max()
    test_retry_rejects_resource_error()
    test_retry_reset()
    print("\n🎉 All self-heal tests passed!")
