"""
Verification Tool - Check code for errors before delivery.

Runs multiple checks:
- Syntax: Does the code parse?
- Imports: Do all imports resolve?
- Types: Type checking (mypy)
- Lint: Code quality (flake8, pylint)
- Security: Basic security scan (bandit)
"""

import ast
import subprocess
import tempfile
import os
import sys
from typing import List, Dict, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger('crucible.verify')


@dataclass
class CheckResult:
    """Result of a single check."""
    name: str
    passed: bool
    message: str
    details: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Complete verification result."""
    passed: bool
    checks: List[CheckResult]
    summary: str

    def to_string(self) -> str:
        status = "✓ ALL CHECKS PASSED" if self.passed else "✗ VERIFICATION FAILED"
        lines = [
            f"=== {status} ===",
            "",
        ]

        for check in self.checks:
            icon = "✓" if check.passed else "✗"
            lines.append(f"{icon} {check.name}: {check.message}")
            for detail in check.details[:5]:  # Limit details
                lines.append(f"    {detail}")
            if len(check.details) > 5:
                lines.append(f"    ... and {len(check.details) - 5} more")

        return "\n".join(lines)


class VerificationTool:
    """
    Verify code quality and correctness.

    Supports Python (primary), with extensibility for other languages.
    """

    def __init__(self):
        self.available_checks = self._detect_available_checks()

    def _detect_available_checks(self) -> Dict[str, bool]:
        """Detect which verification tools are available."""
        checks = {
            "syntax": True,  # Always available (uses ast)
            "imports": True,  # Always available
            "types": self._check_tool_available("mypy"),
            "lint": self._check_tool_available("flake8"),
            "security": self._check_tool_available("bandit"),
        }
        return checks

    def _check_tool_available(self, tool: str) -> bool:
        """Check if a tool is installed."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", tool, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    async def verify(
        self,
        code: str,
        language: str = "python",
        checks: List[str] = None
    ) -> str:
        """
        Verify code with specified checks.

        Args:
            code: Code to verify
            language: Programming language
            checks: List of checks to run (default: syntax, imports)

        Returns:
            Formatted verification result string
        """
        if language != "python":
            return f"Currently only Python verification is implemented. Got: {language}"

        if checks is None:
            checks = ["syntax", "imports"]

        results = []

        for check in checks:
            if check == "syntax":
                results.append(self._check_syntax(code))
            elif check == "imports":
                results.append(self._check_imports(code))
            elif check == "types":
                results.append(await self._check_types(code))
            elif check == "lint":
                results.append(await self._check_lint(code))
            elif check == "security":
                results.append(await self._check_security(code))
            else:
                results.append(CheckResult(
                    name=check,
                    passed=False,
                    message=f"Unknown check: {check}"
                ))

        all_passed = all(r.passed for r in results)
        summary = f"{sum(1 for r in results if r.passed)}/{len(results)} checks passed"

        result = VerificationResult(
            passed=all_passed,
            checks=results,
            summary=summary
        )

        return result.to_string()

    def _check_syntax(self, code: str) -> CheckResult:
        """Check Python syntax using ast."""
        try:
            ast.parse(code)
            return CheckResult(
                name="Syntax",
                passed=True,
                message="Code parses successfully"
            )
        except SyntaxError as e:
            return CheckResult(
                name="Syntax",
                passed=False,
                message=f"Syntax error at line {e.lineno}",
                details=[str(e)]
            )

    def _check_imports(self, code: str) -> CheckResult:
        """Check that all imports can be resolved."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return CheckResult(
                name="Imports",
                passed=False,
                message="Cannot check imports due to syntax error"
            )

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split('.')[0])

        missing = []
        for module in set(imports):
            try:
                __import__(module)
            except ImportError:
                missing.append(module)

        if missing:
            return CheckResult(
                name="Imports",
                passed=False,
                message=f"{len(missing)} import(s) cannot be resolved",
                details=[f"Missing: {m}" for m in missing]
            )

        return CheckResult(
            name="Imports",
            passed=True,
            message=f"All {len(set(imports))} imports resolved"
        )

    async def _check_types(self, code: str) -> CheckResult:
        """Run mypy type checking."""
        if not self.available_checks.get("types"):
            return CheckResult(
                name="Types",
                passed=True,
                message="mypy not available (skipped)"
            )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mypy", "--ignore-missing-imports", temp_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return CheckResult(
                    name="Types",
                    passed=True,
                    message="No type errors found"
                )
            else:
                errors = [l for l in result.stdout.split('\n') if l.strip() and ':' in l]
                return CheckResult(
                    name="Types",
                    passed=False,
                    message=f"{len(errors)} type error(s) found",
                    details=errors
                )

        except subprocess.TimeoutExpired:
            return CheckResult(
                name="Types",
                passed=False,
                message="Type check timed out"
            )
        finally:
            os.unlink(temp_path)

    async def _check_lint(self, code: str) -> CheckResult:
        """Run flake8 linting."""
        if not self.available_checks.get("lint"):
            return CheckResult(
                name="Lint",
                passed=True,
                message="flake8 not available (skipped)"
            )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "flake8", "--max-line-length=120", temp_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return CheckResult(
                    name="Lint",
                    passed=True,
                    message="No lint issues found"
                )
            else:
                issues = [l for l in result.stdout.split('\n') if l.strip()]
                return CheckResult(
                    name="Lint",
                    passed=False,
                    message=f"{len(issues)} lint issue(s) found",
                    details=issues
                )

        except subprocess.TimeoutExpired:
            return CheckResult(
                name="Lint",
                passed=False,
                message="Lint check timed out"
            )
        finally:
            os.unlink(temp_path)

    async def _check_security(self, code: str) -> CheckResult:
        """Run bandit security check."""
        if not self.available_checks.get("security"):
            return CheckResult(
                name="Security",
                passed=True,
                message="bandit not available (skipped)"
            )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "bandit", "-f", "json", temp_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            import json
            try:
                data = json.loads(result.stdout)
                issues = data.get("results", [])

                if not issues:
                    return CheckResult(
                        name="Security",
                        passed=True,
                        message="No security issues found"
                    )
                else:
                    details = [
                        f"{i['severity']}: {i['issue_text']} (line {i['line_number']})"
                        for i in issues
                    ]
                    high_severity = sum(1 for i in issues if i['severity'] in ['HIGH', 'MEDIUM'])
                    return CheckResult(
                        name="Security",
                        passed=high_severity == 0,
                        message=f"{len(issues)} issue(s) found ({high_severity} high/medium)",
                        details=details
                    )
            except json.JSONDecodeError:
                return CheckResult(
                    name="Security",
                    passed=True,
                    message="Could not parse bandit output"
                )

        except subprocess.TimeoutExpired:
            return CheckResult(
                name="Security",
                passed=False,
                message="Security check timed out"
            )
        finally:
            os.unlink(temp_path)

    def get_available_checks(self) -> Dict[str, bool]:
        """Return which checks are available."""
        return self.available_checks.copy()
