"""FailureNormalizer — extracts structured failure context from Playwright errors and reports.

Converts Playwright test output into a clean, normalized TestFailureInfo object
suitable for deterministic analysis and LLM diagnosis without dumping noisy raw logs.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from travelguard.models import TestFailureInfo

logger = logging.getLogger("travelguard.failure_normalizer")

LOCATOR_PATTERNS = [
    r"(getByRole\([^)]+\))",
    r"(getByLabel\([^)]+\))",
    r"(getByText\([^)]+\))",
    r"(getByPlaceholder\([^)]+\))",
    r"(getByTestId\([^)]+\))",
    r"(locator\('[^']+'\))",
    r'(locator\("[^"]+"\))',
    r'(\[data-testid="[^"]+"\])',
    r"(\[data-testid='[^']+'\])",
]


def extract_locator_from_error(text: str) -> Optional[str]:
    """Attempt to extract a Playwright locator expression from error message and stack trace."""
    if not text:
        return None
    for pattern in LOCATOR_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def extract_test_source_snippet(
    test_file_path: Optional[Path],
    failure_line: Optional[int],
    context: int = 5,
) -> Optional[str]:
    """Return source lines around the failure line from the test file with line numbers and a marker."""
    try:
        if not test_file_path or not test_file_path.exists():
            return None
        lines = test_file_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return None
        if failure_line is None:
            return "\n".join(lines[:30])
        start = max(0, failure_line - context - 1)
        end = min(len(lines), failure_line + context)
        snippet_lines = []
        for i, line in enumerate(lines[start:end], start=start + 1):
            marker = ">>>" if i == failure_line else "   "
            snippet_lines.append(f"{i:4d} {marker} {line}")
        return "\n".join(snippet_lines)
    except Exception as exc:
        logger.debug(f"Failed to read source snippet from {test_file_path}: {exc}")
        return None


def extract_expected_and_actual(error_message: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract Expected and Actual/Received values from assertion failure text."""
    expected = None
    actual = None
    if not error_message:
        return expected, actual

    exp_m = re.search(r"Expected[:\s]+(.+)", error_message)
    if exp_m:
        expected = exp_m.group(1).strip()[:300]

    act_m = re.search(r"(?:Received|Actual)[:\s]+(.+)", error_message)
    if act_m:
        actual = act_m.group(1).strip()[:300]

    return expected, actual


def extract_failure_line_number(stack_trace: str) -> Optional[int]:
    """Extract line number of the failure point from a TypeScript/JavaScript stack trace."""
    if not stack_trace:
        return None
    match = re.search(r":(\d+):\d+\)?$", stack_trace, re.MULTILINE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


class FailureNormalizer:
    """Normalizes raw Playwright JSON or string outputs into structured TestFailureInfo."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root

    def normalize(
        self,
        test_id: str,
        test_name: str,
        test_file: str,
        raw_error: Optional[str] = None,
        stdout: str = "",
        stderr: str = "",
        json_spec: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0,
        test_file_abs: Optional[Path] = None,
    ) -> TestFailureInfo:
        """Construct a normalized TestFailureInfo object."""
        error_message = raw_error or ""
        stack_trace = ""
        screenshot_path = None
        trace_path = None

        if json_spec:
            spec_results = json_spec.get("results", [])
            primary = spec_results[0] if spec_results else {}
            err_dict = primary.get("error", {})
            if not error_message:
                error_message = err_dict.get("message", "") or stderr or stdout or "Unknown failure"
            stack_trace = err_dict.get("stack", "")
            duration_ms = primary.get("duration", duration_ms)

            for att in primary.get("attachments", []):
                ct = att.get("contentType", "")
                name = att.get("name", "").lower()
                if ct.startswith("image/"):
                    screenshot_path = att.get("path")
                elif "trace" in name:
                    trace_path = att.get("path")

        if not stack_trace and stderr:
            stack_trace = stderr

        failure_line = extract_failure_line_number(stack_trace)
        locator_used = extract_locator_from_error(f"{error_message}\n{stack_trace}")
        expected, actual = extract_expected_and_actual(error_message)

        source_snippet = None
        if test_file_abs:
            source_snippet = extract_test_source_snippet(test_file_abs, failure_line)

        return TestFailureInfo(
            test_id=test_id,
            test_name=test_name,
            test_file=test_file,
            error_message=error_message[:4000],
            stack_trace=stack_trace[:4000] if stack_trace else None,
            failure_line=failure_line,
            locator_used=locator_used,
            expected_value=expected,
            actual_value=actual,
            screenshot_path=screenshot_path,
            trace_path=trace_path,
            duration_ms=duration_ms,
            stdout=stdout[:2000] if stdout else None,
            stderr=stderr[:2000] if stderr else None,
            source_snippet=source_snippet,
        )


def normalize_failure(
    test_id: str,
    test_name: str,
    test_file: str,
    raw_error: Optional[str] = None,
    stdout: str = "",
    stderr: str = "",
    json_spec: Optional[Dict[str, Any]] = None,
    duration_ms: int = 0,
    test_file_abs: Optional[Path] = None,
) -> TestFailureInfo:
    """Helper functional wrapper for FailureNormalizer."""
    normalizer = FailureNormalizer()
    return normalizer.normalize(
        test_id=test_id,
        test_name=test_name,
        test_file=test_file,
        raw_error=raw_error,
        stdout=stdout,
        stderr=stderr,
        json_spec=json_spec,
        duration_ms=duration_ms,
        test_file_abs=test_file_abs,
    )
