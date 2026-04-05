"""AST-based security validator for generated tool code.

Walks the Python AST to detect dangerous patterns before sandbox execution.
"""

import ast
from dataclasses import dataclass, field
from typing import List

from .. import config


@dataclass
class ValidationResult:
    safe: bool
    violations: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.safe:
            return "✅ Code passed security validation"
        lines = ["❌ Security violations found:"]
        for v in self.violations:
            lines.append(f"  - {v}")
        return "\n".join(lines)


class _SecurityVisitor(ast.NodeVisitor):
    """AST visitor that collects security violations."""

    def __init__(self) -> None:
        self.violations: List[str] = []

    # ── import / importfrom ──────────────────────────────────────
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in config.BLOCKED_MODULES:
                self.violations.append(
                    f"Blocked import: '{alias.name}' (line {node.lineno})"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top = node.module.split(".")[0]
            if top in config.BLOCKED_MODULES:
                self.violations.append(
                    f"Blocked import: 'from {node.module}' (line {node.lineno})"
                )
        self.generic_visit(node)

    # ── dangerous builtins: eval / exec / __import__ ─────────────
    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node)
        if name in config.BLOCKED_BUILTINS:
            self.violations.append(
                f"Blocked builtin call: '{name}()' (line {node.lineno})"
            )
        # open() path check — warn about absolute paths outside sandbox
        if name == "open" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                path = arg.value
                sandbox = str(config.SANDBOX_DIR)
                if path.startswith("/") and not path.startswith(sandbox) and not path.startswith("/tmp"):
                    self.violations.append(
                        f"File access outside sandbox: '{path}' (line {node.lineno})"
                    )
        self.generic_visit(node)

    # ── attribute access: os.system, subprocess.run etc. ─────────
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            if node.value.id in config.BLOCKED_MODULES:
                self.violations.append(
                    f"Blocked module attribute: '{node.value.id}.{node.attr}' (line {node.lineno})"
                )
        self.generic_visit(node)

    # ── helpers ──────────────────────────────────────────────────
    @staticmethod
    def _call_name(node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""


def validate_code(source: str) -> ValidationResult:
    """Validate Python source code for security issues using AST analysis."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return ValidationResult(safe=False, violations=[f"SyntaxError: {e}"])

    visitor = _SecurityVisitor()
    visitor.visit(tree)
    return ValidationResult(safe=len(visitor.violations) == 0, violations=visitor.violations)
