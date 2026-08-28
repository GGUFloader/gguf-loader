"""
AutoTest - Detect and run tests after agent code changes.

Pattern from: Aider's auto-test + SWE-agent's bash -n validation.
After the agent edits code files, this module automatically detects
the project's test framework and runs relevant tests. Results are
fed back to the agent for self-correction.

Features:
- Auto-detect test framework (pytest, unittest, npm, cargo, etc.)
- Run only tests related to changed files
- Capture and format test output
- Configurable test commands per project
- Pass/fail tracking per session
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Test framework detection patterns
TEST_FRAMEWORKS = {
    "pytest": {
        "detect_files": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
        "detect_cmd": "pytest",
        "test_pattern": "test_*.py",
        "cmd": "python -m pytest {tests} -x -q --tb=short",
        "timeout": 120,
    },
    "unittest": {
        "detect_files": [],
        "detect_cmd": "python -m unittest",
        "test_pattern": "test_*.py",
        "cmd": "python -m unittest discover -s {dir} -p 'test_*.py' -v",
        "timeout": 120,
    },
    "npm": {
        "detect_files": ["package.json"],
        "detect_cmd": "npm test",
        "test_pattern": "*.test.{js,ts,jsx,tsx}",
        "cmd": "npm test",
        "timeout": 120,
    },
    "cargo": {
        "detect_files": ["Cargo.toml"],
        "detect_cmd": "cargo test",
        "test_pattern": "*.rs",
        "cmd": "cargo test",
        "timeout": 120,
    },
    "go": {
        "detect_files": ["go.mod"],
        "detect_cmd": "go test",
        "test_pattern": "*_test.go",
        "cmd": "go test ./...",
        "timeout": 120,
    },
}


class TestResult:
    """Result of a test run."""

    def __init__(self, framework: str, passed: int, failed: int, errors: int,
                 output: str, duration_ms: int = 0, test_files: List[str] = None) -> None:
        self.framework = framework
        self.passed = passed
        self.failed = failed
        self.errors = errors
        self.output = output
        self.duration_ms = duration_ms
        self.test_files = test_files or []

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.errors == 0

    @property
    def summary(self) -> str:
        total = self.passed + self.failed + self.errors
        if self.success:
            return f"✅ {self.passed}/{total} tests passed ({self.framework})"
        return f"❌ {self.failed} failed, {self.errors} errors, {self.passed} passed ({self.framework})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "output": self.output[:2000],
            "test_files": self.test_files,
        }


class AutoTest:
    """Detect and run tests after agent code changes.

    Usage:
        at = AutoTest(workspace_path)
        at.auto_detect()

        # After agent edits code
        result = at.run_tests_for_files(["src/foo.py", "src/bar.py"])
        if not result.success:
            print(result.output)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._framework: Optional[str] = None
        self._config: Optional[Dict[str, Any]] = None
        self._custom_cmd: Optional[str] = None
        self._results: List[TestResult] = []

    def auto_detect(self) -> Optional[str]:
        """Auto-detect the test framework for this project.

        Returns:
            Framework name if detected, None otherwise.
        """
        # Check for custom test command in project config
        custom = self._load_custom_config()
        if custom:
            self._custom_cmd = custom
            self._framework = "custom"
            return "custom"

        # Detect by files
        for framework, config in TEST_FRAMEWORKS.items():
            for detect_file in config["detect_files"]:
                if (self.workspace / detect_file).exists():
                    self._framework = framework
                    self._config = config
                    logger.info("Detected test framework: %s", framework)
                    return framework

        # Detect by trying commands
        for framework, config in TEST_FRAMEWORKS.items():
            try:
                result = subprocess.run(
                    config["detect_cmd"].split()[:3],  # just check if command exists
                    cwd=str(self.workspace),
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode in (0, 2, 5):  # 2 = no tests found, 5 = no tests collected
                    self._framework = framework
                    self._config = config
                    logger.info("Detected test framework: %s (by command)", framework)
                    return framework
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue

        return None

    def _load_custom_config(self) -> Optional[str]:
        """Load custom test command from project config."""
        # Check .ggufloader.json
        config_file = self.workspace / ".ggufloader.json"
        if config_file.exists():
            try:
                import json
                config = json.loads(config_file.read_text(encoding="utf-8"))
                cmd = config.get("test_command")
                if cmd:
                    return cmd
            except Exception:
                pass

        # Check package.json scripts.test
        pkg_file = self.workspace / "package.json"
        if pkg_file.exists():
            try:
                import json
                pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
                test_script = (pkg.get("scripts") or {}).get("test")
                if test_script:
                    return f"npm test"
            except Exception:
                pass

        return None

    def set_framework(self, framework: str, cmd: str = None) -> None:
        """Manually set the test framework."""
        self._framework = framework
        if cmd:
            self._custom_cmd = cmd
        elif framework in TEST_FRAMEWORKS:
            self._config = TEST_FRAMEWORKS[framework]

    def run_tests(self, cmd: str = None, timeout: int = 120) -> TestResult:
        """Run all tests with the detected framework.

        Args:
            cmd: Override command (uses detected framework if None)
            timeout: Max seconds to wait

        Returns:
            TestResult with pass/fail counts and output.
        """
        command = cmd or self._custom_cmd
        if not command and self._config:
            test_files = self._find_test_files()
            command = self._config["cmd"].format(
                tests=" ".join(str(f) for f in test_files[:20]),
                dir=str(self.workspace),
            )
            timeout = self._config.get("timeout", timeout)

        if not command:
            return TestResult(
                framework="none", passed=0, failed=0, errors=1,
                output="No test framework detected. Set one with set_framework() "
                       "or add a test_command to .ggufloader.json",
            )

        return self._run_command(command, timeout)

    def run_tests_for_files(self, changed_files: List[str], timeout: int = 120) -> TestResult:
        """Run tests related to specific changed files.

        For Python: runs tests that import from the changed modules.
        For JS/TS: runs tests in the same directory.
        Falls back to running all tests if specific tests can't be determined.
        """
        if not self._framework and not self._custom_cmd:
            self.auto_detect()

        # Find related test files
        test_files = []
        for f in changed_files:
            path = Path(f)
            # Python: test_foo.py for foo.py
            if path.suffix == ".py":
                test_name = f"test_{path.stem}.py"
                for test_dir in [path.parent, Path("tests"), Path("test")]:
                    candidate = test_dir / test_name
                    if candidate.exists():
                        test_files.append(candidate)
            # JS/TS: foo.test.js for foo.js
            elif path.suffix in (".js", ".ts", ".jsx", ".tsx"):
                for ext in [".test", ".spec"]:
                    for lang_ext in [".js", ".ts"]:
                        candidate = path.with_suffix(ext + lang_ext)
                        if candidate.exists():
                            test_files.append(candidate)

        if test_files:
            # Run specific tests
            if self._framework == "pytest":
                cmd = f"python -m pytest {' '.join(str(f) for f in test_files)} -x -q --tb=short"
            elif self._custom_cmd:
                cmd = self._custom_cmd
            else:
                return self.run_tests(timeout=timeout)

            result = self._run_command(cmd, timeout)
            result.test_files = [str(f) for f in test_files]
            return result

        # Fallback: run all tests
        return self.run_tests(timeout=timeout)

    def _run_command(self, command: str, timeout: int) -> TestResult:
        """Execute a test command and parse results."""
        import time as _time
        start = _time.monotonic()

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            elapsed = int((_time.monotonic() - start) * 1000)
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            output = output.strip()

            passed, failed, errors = self._parse_output(proc.returncode, output)

            result = TestResult(
                framework=self._framework or "custom",
                passed=passed,
                failed=failed,
                errors=errors,
                output=output[:3000],
                duration_ms=elapsed,
            )
            self._results.append(result)
            return result

        except subprocess.TimeoutExpired:
            elapsed = int((_time.monotonic() - start) * 1000)
            return TestResult(
                framework=self._framework or "custom",
                passed=0, failed=0, errors=1,
                output=f"Tests timed out after {timeout}s",
                duration_ms=elapsed,
            )
        except Exception as e:
            return TestResult(
                framework=self._framework or "custom",
                passed=0, failed=0, errors=1,
                output=f"Test execution error: {e}",
            )

    def _parse_output(self, returncode: int, output: str) -> tuple[int, int, int]:
        """Parse test output to extract pass/fail/error counts."""
        passed = failed = errors = 0

        # pytest format: "X passed, Y failed, Z errors"
        import re
        m = re.search(r"(\d+) passed", output)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", output)
        if m:
            failed = int(m.group(1))
        m = re.search(r"(\d+) error", output)
        if m:
            errors = int(m.group(1))

        # unittest format: "Ran N tests" + "FAILED" or "OK"
        if passed == 0 and failed == 0:
            m = re.search(r"Ran (\d+) tests?", output)
            if m:
                total = int(m.group(1))
                if "OK" in output:
                    passed = total
                elif "FAILED" in output:
                    failed_lines = re.findall(r"FAIL:", output)
                    failed = len(failed_lines) if failed_lines else total
                    passed = total - failed

        # npm/jest format: "Tests: X failed, Y total"
        m = re.search(r"Tests:\s+(\d+)\s+failed.*?(\d+)\s+total", output)
        if m:
            failed = int(m.group(1))
            total = int(m.group(2))
            passed = total - failed

        # cargo test format
        m = re.search(r"test result: (ok|FAILED)\. (\d+) passed.*?(\d+) failed", output)
        if m:
            passed = int(m.group(2))
            failed = int(m.group(3))

        return passed, failed, errors

    def _find_test_files(self) -> List[Path]:
        """Find all test files in the workspace."""
        if not self._config:
            return []
        pattern = self._config.get("test_pattern", "test_*.py")
        return list(self.workspace.rglob(pattern))[:50]

    def get_results(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._results]

    def get_stats(self) -> Dict[str, Any]:
        total_runs = len(self._results)
        total_passed = sum(r.passed for r in self._results)
        total_failed = sum(r.failed for r in self._results)
        return {
            "framework": self._framework,
            "total_runs": total_runs,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "last_result": self._results[-1].to_dict() if self._results else None,
        }
