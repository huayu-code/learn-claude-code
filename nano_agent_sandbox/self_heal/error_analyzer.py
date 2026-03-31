"""
error_analyzer.py — 错误分析器

职责：
  1. 分类错误类型（语法 / 运行时 / 依赖缺失 / 超时）
  2. 根据错误类型生成针对性的修复建议
  3. 将分析结果注入上下文，指导 LLM 自愈
"""
import re

# ── 错误分类体系 ─────────────────────────────────────

ERROR_CATEGORIES = {
    "syntax": {
        "patterns": ["SyntaxError", "IndentationError", "TabError"],
        "description": "代码语法错误",
        "severity": "high",  # 必须修复，否则无法执行
    },
    "import": {
        "patterns": ["ImportError", "ModuleNotFoundError"],
        "description": "依赖缺失",
        "severity": "medium",  # 可能通过 pip install 修复
    },
    "runtime": {
        "patterns": [
            "NameError", "TypeError", "ValueError", "AttributeError",
            "IndexError", "KeyError", "ZeroDivisionError",
        ],
        "description": "运行时错误",
        "severity": "medium",
    },
    "io": {
        "patterns": ["FileNotFoundError", "PermissionError", "OSError", "IOError"],
        "description": "文件/IO 错误",
        "severity": "medium",
    },
    "resource": {
        "patterns": ["MemoryError", "RecursionError"],
        "description": "资源耗尽",
        "severity": "high",  # 需要算法层面修改
    },
    "timeout": {
        "patterns": ["TimeoutError", "TIMEOUT"],
        "description": "执行超时",
        "severity": "high",
    },
}


class ErrorAnalyzer:
    """错误分析器"""

    def classify_error(self, error_text: str) -> dict:
        """
        分析错误文本，返回结构化的错误信息。

        Returns:
            {
                "type": "syntax" | "import" | "runtime" | ...,
                "error_name": "SyntaxError",
                "message": "具体错误信息",
                "severity": "high" | "medium" | "low",
                "line_number": 可选的行号,
            }
        """
        error_info = {
            "type": "unknown",
            "error_name": "UnknownError",
            "message": error_text[:500],
            "severity": "medium",
            "line_number": None,
        }

        # 匹配分类
        for category, config in ERROR_CATEGORIES.items():
            for pattern in config["patterns"]:
                if pattern in error_text:
                    error_info["type"] = category
                    error_info["error_name"] = pattern
                    error_info["severity"] = config["severity"]
                    break
            if error_info["type"] != "unknown":
                break

        # 提取行号（如 "line 42"）
        line_match = re.search(r"line (\d+)", error_text)
        if line_match:
            error_info["line_number"] = int(line_match.group(1))

        # 提取具体错误消息
        msg_match = re.search(r"(?:Error|Exception):\s*(.+?)(?:\n|$)", error_text)
        if msg_match:
            error_info["message"] = msg_match.group(1).strip()

        return error_info

    def suggest_fix(self, error_info: dict) -> str:
        """
        根据错误分类生成修复建议。
        这些建议会被注入到 LLM 上下文中，引导其自愈。

        Args:
            error_info: classify_error 返回的结构

        Returns:
            修复建议文本
        """
        error_type = error_info["type"]
        error_name = error_info["error_name"]
        message = error_info["message"]
        line_num = error_info.get("line_number")

        suggestions = {
            "syntax": (
                f"Syntax error{f' at line {line_num}' if line_num else ''}: {message}\n"
                "Fix: Check indentation, brackets, quotes, and colons. "
                "Rewrite the code with correct syntax."
            ),
            "import": (
                f"Missing module: {message}\n"
                "Fix options:\n"
                "1. Use `bash` tool to install: pip install <package>\n"
                "2. Use a standard library alternative\n"
                "3. Implement the needed functionality manually"
            ),
            "runtime": (
                f"Runtime error ({error_name}): {message}\n"
                "Fix: Check variable names, types, and data structures. "
                "Add type checks or try/except if needed."
            ),
            "io": (
                f"File/IO error: {message}\n"
                "Fix: Verify the file path exists and is accessible. "
                "Use the sandbox workspace directory for file operations."
            ),
            "resource": (
                f"Resource error ({error_name}): {message}\n"
                "Fix: Optimize the algorithm. Reduce data size, add iteration limits, "
                "or process data in chunks."
            ),
            "timeout": (
                "Execution timed out.\n"
                "Fix: The code is too slow. Optimize loops, reduce data size, "
                "or break into smaller steps."
            ),
        }

        return suggestions.get(error_type, f"Unknown error: {message}\nFix: Review the code and try a different approach.")
