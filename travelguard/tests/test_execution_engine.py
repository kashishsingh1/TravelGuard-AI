"""Unit tests for TestExecutionEngine.

All tests mock subprocess calls — no live Playwright or browser required.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from travelguard.execution_engine import TestExecutionEngine
from travelguard.models import SelectedTest, TestExecutionResult, TestPriority


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_selected_test(test_id: str = "booking-drift", file: str = "tests/e2e/booking-drift.spec.ts") -> SelectedTest:
    return SelectedTest(
        test_id=test_id,
        file=file,
        name="Flight Booking Drift Detection",
        priority=TestPriority.P0,
        reason="Critical booking journey affected",
        confidence=0.95,
    )


def _make_playwright_json_report(status: str = "passed") -> dict:
    """Build a minimal Playwright JSON reporter output."""
    return {
        "suites": [
            {
                "title": "booking-drift.spec.ts",
                "file": "tests/e2e/booking-drift.spec.ts",
                "specs": [
                    {
                        "title": "Flight Booking Drift Detection",
                        "ok": status == "passed",
                        "tests": [
                            {
                                "title": "Flight Booking Drift Detection",
                                "status": status,
                                "duration": 1540,
                                "results": [
                                    {
                                        "status": status,
                                        "duration": 1540,
                                        "errors": [] if status == "passed" else [
                                            {
                                                "message": "Error: getByRole('button', { name: 'Book Flight' }) not found",
                                                "stack": "Error: ...\n    at tests/e2e/booking-drift.spec.ts:25:56",
                                            }
                                        ],
                                        "attachments": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExecutionEngineInit:
    def test_creates_artifacts_dirs(self, tmp_path: Path) -> None:
        engine = TestExecutionEngine(
            tests_dir=tmp_path / "tests",
            repo_root=tmp_path,
            artifacts_dir=tmp_path / "artifacts",
        )
        assert (tmp_path / "artifacts" / "runs").exists()
        assert (tmp_path / "artifacts" / "failures").exists()
        assert (tmp_path / "artifacts" / "healing").exists()

    def test_default_timeout(self, tmp_path: Path) -> None:
        engine = TestExecutionEngine(repo_root=tmp_path, artifacts_dir=tmp_path / "artifacts")
        assert engine.timeout_seconds == 120


class TestExecutionEngineResolveTestFile:
    def test_resolves_relative_path(self, tmp_path: Path) -> None:
        test_file = tmp_path / "tests" / "e2e" / "booking.spec.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("// test")

        engine = TestExecutionEngine(repo_root=tmp_path, artifacts_dir=tmp_path / "artifacts")
        resolved = engine._resolve_test_file_abs("tests/e2e/booking.spec.ts")
        assert resolved is not None
        assert resolved == test_file


class TestExecutionEngineExecute:
    @patch("subprocess.run")
    def test_passed_test_returns_passed_result(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """A test that passes should return status='passed' with no failure."""
        report = _make_playwright_json_report("passed")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(report),
            stderr="",
        )

        # Create dummy test file
        test_file = tmp_path / "tests" / "e2e" / "booking-drift.spec.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test('booking-drift', async ({ page }) => {});")

        engine = TestExecutionEngine(
            tests_dir=tmp_path / "tests",
            repo_root=tmp_path,
            artifacts_dir=tmp_path / "artifacts",
        )
        selected = [_make_selected_test()]
        results = engine.execute(selected)

        assert len(results) == 1
        assert results[0].status == "passed"
        assert results[0].failure is None

    @patch("subprocess.run")
    def test_failed_test_returns_failed_result(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """A test that fails should return status='failed' with failure populated."""
        report = _make_playwright_json_report("failed")
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps(report),
            stderr="",
        )

        test_file = tmp_path / "tests" / "e2e" / "booking-drift.spec.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test('booking-drift', async ({ page }) => {});")

        engine = TestExecutionEngine(
            tests_dir=tmp_path / "tests",
            repo_root=tmp_path,
            artifacts_dir=tmp_path / "artifacts",
        )
        selected = [_make_selected_test()]
        results = engine.execute(selected)

        assert len(results) == 1
        assert results[0].status == "failed"
        assert results[0].failure is not None

    @patch("subprocess.run")
    def test_subprocess_timeout_returns_failed(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """A subprocess.TimeoutExpired should produce a failed result."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="npx", timeout=120)

        test_file = tmp_path / "tests" / "e2e" / "booking-drift.spec.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test('booking-drift', async ({ page }) => {});")

        engine = TestExecutionEngine(
            tests_dir=tmp_path / "tests",
            repo_root=tmp_path,
            artifacts_dir=tmp_path / "artifacts",
            timeout_seconds=120,
        )
        selected = [_make_selected_test()]
        results = engine.execute(selected)

        assert len(results) == 1
        assert results[0].status in {"failed", "timedOut"}

    def test_missing_test_file_returns_failed(self, tmp_path: Path) -> None:
        """If the test file cannot be resolved, the engine should report failure."""
        engine = TestExecutionEngine(
            tests_dir=tmp_path / "nonexistent",
            repo_root=tmp_path,
            artifacts_dir=tmp_path / "artifacts",
        )
        selected = [_make_selected_test(file="tests/e2e/no-such-file.spec.ts")]
        results = engine.execute(selected)

        assert len(results) == 1
        assert results[0].status == "failed"

    @patch("subprocess.run")
    def test_multiple_tests_returned_in_order(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """execute() should return one result per selected test."""
        report = _make_playwright_json_report("passed")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(report),
            stderr="",
        )

        tests_dir = tmp_path / "tests" / "e2e"
        tests_dir.mkdir(parents=True)
        for name in ["booking.spec.ts", "search.spec.ts"]:
            (tests_dir / name).write_text("// test")

        engine = TestExecutionEngine(
            tests_dir=tmp_path / "tests",
            repo_root=tmp_path,
            artifacts_dir=tmp_path / "artifacts",
        )
        selected = [
            _make_selected_test("booking", "tests/e2e/booking.spec.ts"),
            _make_selected_test("search", "tests/e2e/search.spec.ts"),
        ]
        results = engine.execute(selected)
        assert len(results) == 2
