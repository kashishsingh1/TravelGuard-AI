"""TestExecutionEngine — executes selected Playwright tests and returns structured results.

Uses the existing tests/playwright.config.ts. Invokes npx playwright test with JSON reporter
for structured parsing. Returns TestExecutionResult with full failure context per test file.
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("travelguard.execution")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _REPO_ROOT / "tests"


from travelguard.failure_normalizer import (
    FailureNormalizer,
    extract_locator_from_error as _extract_locator_from_error,
    extract_test_source_snippet as _extract_test_source_snippet,
)


class TestExecutionEngine:
    """
    Executes selected Playwright tests using the existing playwright.config.ts.

    Input:  List[SelectedTest]
    Output: List[TestExecutionResult]
    """

    __test__ = False

    def __init__(
        self,
        tests_dir: Optional[Path] = None,
        repo_root: Optional[Path] = None,
        timeout_seconds: int = 120,
        artifacts_dir: Optional[Path] = None,
    ):
        self.tests_dir = tests_dir or _TESTS_DIR
        self.repo_root = repo_root or _REPO_ROOT
        self.timeout_seconds = timeout_seconds
        self.artifacts_dir = artifacts_dir or (self.repo_root / "artifacts")
        self._ensure_artifacts_dirs()

    def _ensure_artifacts_dirs(self) -> None:
        """Create artifact storage directories on demand."""
        for sub in ["runs", "failures", "healing", "screenshots", "traces"]:
            (self.artifacts_dir / sub).mkdir(parents=True, exist_ok=True)

    def _resolve_test_file_abs(self, file_path: str) -> Optional[Path]:
        """Resolve a test file path to an absolute Path object."""
        p = Path(file_path)
        if p.is_absolute() and p.exists():
            return p
        candidate = self.repo_root / file_path
        if candidate.exists():
            return candidate
        candidate2 = self.tests_dir / p.name
        if candidate2.exists():
            return candidate2
        logger.warning(f"[ExecutionEngine] Test file not found: {file_path}")
        return None

    def _run_playwright(self, rel_test_file: str, extra_env: Optional[dict] = None) -> Tuple[int, str, str, dict]:
        """
        Run Playwright for a single test file from within the tests/ directory.
        Returns (exit_code, stdout, stderr, json_report_dict).
        """
        json_out_file = self.artifacts_dir / "runs" / f"pw_result_{int(time.time() * 1000)}.json"

        config_path = self.tests_dir / "playwright.config.ts"
        cmd = [
            "npx", "playwright", "test", rel_test_file,
            "--config", str(config_path),
            "--reporter=json,list",
        ]

        env = dict(os.environ)
        env.setdefault("PLAYWRIGHT_BASE_URL", "http://localhost:5173")
        env.setdefault("BACKEND_URL", "http://localhost:8000")
        env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = str(json_out_file)
        if extra_env:
            env.update(extra_env)

        logger.info(f"[ExecutionEngine] Command: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.tests_dir),
                capture_output=True,
                text=True,
                timeout=min(self.timeout_seconds, 35),
                shell=(sys.platform == "win32"),
                env=env,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_code = proc.returncode

            json_report: dict = {}
            if json_out_file.exists():
                try:
                    json_report = json.loads(json_out_file.read_text(encoding="utf-8"))
                except Exception as pe:
                    logger.warning(f"[ExecutionEngine] JSON report parse error: {pe}")

            return exit_code, stdout, stderr, json_report

        except subprocess.TimeoutExpired:
            logger.error(f"[ExecutionEngine] Timed out after {self.timeout_seconds}s: {rel_test_file}")
            return -1, "", f"Timeout after {self.timeout_seconds}s", {}
        except FileNotFoundError:
            logger.error("[ExecutionEngine] npx/playwright not found — check environment setup")
            return -2, "", "playwright/npx not found: ENVIRONMENT_FAILURE", {}
        except OSError as e:
            logger.error(f"[ExecutionEngine] OS error running playwright: {e}")
            return -2, "", f"OS error: {e}: ENVIRONMENT_FAILURE", {}

    def _flatten_specs(self, suites: list) -> list:
        """Recursively flatten nested Playwright suite structure into individual spec items."""
        specs = []
        for suite in suites:
            specs.extend(suite.get("specs", []))
            specs.extend(self._flatten_specs(suite.get("suites", [])))
        return specs

    def _build_result(self, test_id: str, test_file: str, test_name: str,
                      exit_code: int, stdout: str, stderr: str, json_report: dict):
        """Convert raw Playwright output into a structured TestExecutionResult."""
        from travelguard.models import TestExecutionResult, TestFailureInfo

        # Environment failure: playwright not found
        if exit_code == -2:
            failure = TestFailureInfo(
                test_id=test_id, test_name=test_name, test_file=test_file,
                error_message="playwright/npx not found: ENVIRONMENT_FAILURE",
                stack_trace=stderr, stderr=stderr,
            )
            return TestExecutionResult(
                test_id=test_id, test_file=test_file, test_name=test_name,
                status="failed", failure=failure, stdout=stdout, stderr=stderr,
            )

        # Timeout
        if exit_code == -1:
            failure = TestFailureInfo(
                test_id=test_id, test_name=test_name, test_file=test_file,
                error_message=f"Test execution timed out after {self.timeout_seconds}s",
                stack_trace=stderr, stderr=stderr,
            )
            return TestExecutionResult(
                test_id=test_id, test_file=test_file, test_name=test_name,
                status="timedOut", failure=failure, stdout=stdout, stderr=stderr,
            )

        # Parse JSON report specs
        suites = json_report.get("suites", [])
        all_specs = self._flatten_specs(suites)

        # Passed
        if exit_code == 0:
            total_duration = sum(
                r.get("duration", 0)
                for s in all_specs for r in s.get("results", [])
            )
            return TestExecutionResult(
                test_id=test_id, test_file=test_file, test_name=test_name,
                status="passed", duration_ms=total_duration,
                stdout=stdout, stderr=stderr,
            )

        # Find first failed spec
        failed_spec = next((s for s in all_specs if s.get("ok") is False), None)
        if failed_spec is None:
            # No JSON detail — build from raw output
            failure = TestFailureInfo(
                test_id=test_id, test_name=test_name, test_file=test_file,
                error_message=(stderr or stdout or "Test failed — no JSON report")[:2000],
                stdout=stdout[:2000], stderr=stderr[:2000],
            )
            return TestExecutionResult(
                test_id=test_id, test_file=test_file, test_name=test_name,
                status="failed", failure=failure, stdout=stdout, stderr=stderr,
            )

        spec_results = failed_spec.get("results", [])
        primary = spec_results[0] if spec_results else {}
        error_info = primary.get("error", {})
        error_message = error_info.get("message", stderr or "Unknown test failure")
        stack_trace = error_info.get("stack", "")
        duration_ms = primary.get("duration", 0)

        # Failure line number from stack trace
        failure_line = None
        line_m = re.search(r":(\d+):\d+\)?$", stack_trace, re.MULTILINE)
        if line_m:
            failure_line = int(line_m.group(1))

        # Locator expression
        locator_used = _extract_locator_from_error(error_message + "\n" + stack_trace)

        # Source snippet around failure
        test_file_abs = self._resolve_test_file_abs(test_file)
        source_snippet = _extract_test_source_snippet(test_file_abs, failure_line)

        # Attachments (screenshots, traces)
        attachments = primary.get("attachments", [])
        screenshot_path = None
        trace_path = None
        for att in attachments:
            ct = att.get("contentType", "")
            name = att.get("name", "").lower()
            if ct.startswith("image/"):
                screenshot_path = att.get("path")
            elif "trace" in name:
                trace_path = att.get("path")

        # Expected / actual from assertion messages
        expected_value = actual_value = None
        exp_m = re.search(r"Expected[:\s]+(.+)", error_message)
        act_m = re.search(r"Received[:\s]+(.+)", error_message)
        if exp_m:
            expected_value = exp_m.group(1).strip()[:200]
        if act_m:
            actual_value = act_m.group(1).strip()[:200]

        failure = TestFailureInfo(
            test_id=test_id,
            test_name=failed_spec.get("title", test_name),
            test_file=test_file,
            status="failed",
            duration_ms=duration_ms,
            error_message=error_message[:2000],
            stack_trace=stack_trace[:3000],
            expected_value=expected_value,
            actual_value=actual_value,
            locator_used=locator_used,
            screenshot_path=screenshot_path,
            trace_path=trace_path,
            test_source_snippet=source_snippet,
            browser="chromium",
            stdout=stdout[:2000],
            stderr=stderr[:2000],
            failure_line=failure_line,
        )

        return TestExecutionResult(
            test_id=test_id, test_file=test_file, test_name=test_name,
            status="failed", duration_ms=duration_ms,
            failure=failure, stdout=stdout[:2000], stderr=stderr[:2000],
            screenshot_path=screenshot_path, trace_path=trace_path,
        )

    def execute(self, selected_tests, extra_env: Optional[dict] = None) -> list:
        """
        Execute a list of SelectedTest objects sequentially.
        Returns list of TestExecutionResult.
        """
        results = []
        for test in selected_tests:
            test_id = getattr(test, "test_id", "unknown")
            test_file = getattr(test, "file", "")
            test_name = getattr(test, "name", test_id)

            logger.info(f"[ExecutionEngine] Executing: [{test_id}] {test_file}")

            # Playwright is run from within tests/ — strip the "tests/" prefix
            rel_file = Path(test_file)
            if rel_file.parts and rel_file.parts[0] == "tests":
                rel_for_playwright = "/".join(rel_file.parts[1:])
            else:
                rel_for_playwright = "/".join(rel_file.parts)

            start_ts = time.monotonic()
            exit_code, stdout, stderr, json_report = self._run_playwright(
                rel_for_playwright, extra_env=extra_env
            )
            elapsed_ms = int((time.monotonic() - start_ts) * 1000)

            result = self._build_result(
                test_id, test_file, test_name,
                exit_code, stdout, stderr, json_report,
            )
            if not result.duration_ms:
                result.duration_ms = elapsed_ms

            results.append(result)
            icon = "PASS" if result.status == "passed" else "FAIL"
            logger.info(f"[ExecutionEngine] [{icon}] {test_name} ({result.duration_ms}ms)")

        return results

    def execute_single_file(self, test_file: str, test_id: str, test_name: str,
                             extra_env: Optional[dict] = None):
        """Execute one test file by path. Used for re-run after self-healing."""
        class _Selected:
            def __init__(self, tid: str, f: str, n: str):
                self.test_id = tid
                self.file = f
                self.name = n

        return self.execute([_Selected(test_id, test_file, test_name)], extra_env=extra_env)[0]
