import ast
from typing import List, Dict, Any
from radon.complexity import cc_visit, ComplexityVisitor


class CodeViolation:
    def __init__(self, line: int, category: str, message: str, severity: str = "WARNING"):
        self.line = line
        self.category = category
        self.message = message
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line": self.line,
            "category": self.category,
            "message": self.message,
            "severity": self.severity,
        }


class StaticASTAnalyzer:
    """Tier-1 Deterministic Inspector: Runs zero-cost local AST rules and complexity analysis."""

    def __init__(self, max_complexity: int = 10):
        self.max_complexity = max_complexity

    def analyze_source(self, code_str: str) -> List[CodeViolation]:
        violations: List[CodeViolation] = []

        # 1. Syntax Verification
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            violations.append(
                CodeViolation(
                    line=e.lineno or 1,
                    category="SYNTAX_ERROR",
                    message=f"Syntax Error: {e.msg}",
                    severity="ERROR",
                )
            )
            return violations

        # 2. Cyclomatic Complexity via Radon
        try:
            complexity_blocks = cc_visit(code_str)
            for block in complexity_blocks:
                if block.complexity > self.max_complexity:
                    violations.append(
                        CodeViolation(
                            line=block.lineno,
                            category="HIGH_COMPLEXITY",
                            message=(
                                f"Function '{block.name}' has high cyclomatic complexity "
                                f"({block.complexity} > {self.max_complexity}). Consider decomposing it."
                            ),
                            severity="WARNING",
                        )
                    )
        except Exception:
            pass

        # 3. Custom AST Rule Checks (e.g., bare excepts, mutable default args)
        for node in ast.walk(tree):
            # Check for bare `except:` clause
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append(
                    CodeViolation(
                        line=node.lineno,
                        category="ANTI_PATTERN",
                        message="Bare 'except:' caught. Specify an explicit Exception class to avoid masking system exits.",
                        severity="WARNING",
                    )
                )

            # Check for mutable default arguments: def func(a=[]) or def func(b={})
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        violations.append(
                            CodeViolation(
                                line=node.lineno,
                                category="SECURITY_BUG",
                                message="Dangerous mutable default argument detected. Use None as default and initialize inside function.",
                                severity="ERROR",
                            )
                        )

        return violations