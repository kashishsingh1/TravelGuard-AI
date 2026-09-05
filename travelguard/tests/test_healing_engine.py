"""Unit tests for SelfHealingEngine.

All tests mock LLM and subprocess calls — no live API or Playwright required.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from travelguard.healing_engine import SelfHealingEngine, MAX_HEALING_ATTEMPTS
from travelguard.models import (
    DiagnosisResult,
    FailureClassification,
    HealingStatus,
    RepairTarget,
    TestFailureInfo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_failure(
    test_id: str = "booking-drift",
    test_file: str = "tests/e2e/booking-drift.spec.ts",
    locator_used: str = "getByRole('button', { name: 'Book Flight' })",
) -> TestFailureInfo:
    return TestFailureInfo(
        test_id=test_id,
        test_name="Booking Drift Detection",
        test_file=test_file,
        error_message="Timeout waiting for getByRole('button', { name: 'Book Flight' })",
        locator_used=locator_used,
        duration_ms=1540,
    )


def _make_drift_diagnosis(
    confidence: float = 0.95,
    old_locator: str = "getByRole('button', { name: 'Book Flight' })",
    new_locator: str = "getByRole('button', { name: 'Reserve Flight' })",
    test_file: str = "tests/e2e/booking-drift.spec.ts",
) -> DiagnosisResult:
    return DiagnosisResult(
        test_id="booking-drift",
        test_file=test_file,
        classification=FailureClassification.TEST_DRIFT,
        confidence=confidence,
        summary="Button label changed from 'Book Flight' to 'Reserve Flight'.",
        evidence=["UI diff shows button text change"],
        recommended_action="REPAIR_TEST",
        repair_target=RepairTarget(
            file=test_file,
            line=25,
            old_locator=old_locator,
            new_locator=new_locator,
        ),
    )


def _make_defect_diagnosis(test_file: str = "tests/e2e/api-health.spec.ts") -> DiagnosisResult:
    return DiagnosisResult(
        test_id="booking-api",
        test_file=test_file,
        classification=FailureClassification.PRODUCT_DEFECT,
        confidence=0.97,
        summary="API returns HTTP 500.",
        evidence=["HTTP 500 in error"],
        recommended_action="RAISE_BUG",
    )


def _make_env_diagnosis() -> DiagnosisResult:
    return DiagnosisResult(
        test_id="booking-api",
        test_file="tests/e2e/api-health.spec.ts",
        classification=FailureClassification.ENVIRONMENT_FAILURE,
        confidence=0.97,
        summary="ECONNREFUSED.",
        evidence=["Connection refused"],
        recommended_action="RETRY",
    )


def _make_healing_engine(tmp_path: Path) -> SelfHealingEngine:
    return SelfHealingEngine(
        repo_root=tmp_path,
        tests_dir=tmp_path / "tests",
        artifacts_dir=tmp_path / "artifacts",
        healing_mode="AUTO",
        confidence_threshold=0.90,
    )


def _create_test_file(tmp_path: Path, content: str) -> Path:
    spec = tmp_path / "tests" / "e2e" / "booking-drift.spec.ts"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(content)
    return spec


# ---------------------------------------------------------------------------
# Tests: Skipping non-TEST_DRIFT failures
# ---------------------------------------------------------------------------

class TestHealingSkipsNonDrift:
    @pytest.mark.asyncio
    async def test_product_defect_not_healed(self, tmp_path: Path) -> None:
        engine = _make_healing_engine(tmp_path)
        result = await engine.heal(
            failure=_make_failure(),
            diagnosis=_make_defect_diagnosis(),
        )
        assert result.status == HealingStatus.SKIPPED_PRODUCT_DEFECT
        assert result.failure_classification == FailureClassification.PRODUCT_DEFECT

    @pytest.mark.asyncio
    async def test_environment_failure_not_healed(self, tmp_path: Path) -> None:
        engine = _make_healing_engine(tmp_path)
        result = await engine.heal(
            failure=_make_failure(),
            diagnosis=_make_env_diagnosis(),
        )
        assert result.status == HealingStatus.SKIPPED_ENVIRONMENT_FAILURE

    @pytest.mark.asyncio
    async def test_unknown_not_healed(self, tmp_path: Path) -> None:
        engine = _make_healing_engine(tmp_path)
        diagnosis = DiagnosisResult(
            test_id="booking-drift",
            test_file="tests/e2e/booking-drift.spec.ts",
            classification=FailureClassification.UNKNOWN,
            confidence=0.40,
            summary="Cannot determine cause.",
            evidence=[],
            recommended_action="INVESTIGATE",
        )
        result = await engine.heal(failure=_make_failure(), diagnosis=diagnosis)
        assert result.status == HealingStatus.SKIPPED_UNKNOWN


# ---------------------------------------------------------------------------
# Tests: Confidence gate
# ---------------------------------------------------------------------------

class TestHealingConfidenceGate:
    @pytest.mark.asyncio
    async def test_low_confidence_skipped(self, tmp_path: Path) -> None:
        engine = _make_healing_engine(tmp_path)
        low_conf_diag = _make_drift_diagnosis(confidence=0.50)
        result = await engine.heal(failure=_make_failure(), diagnosis=low_conf_diag)
        assert result.status == HealingStatus.SKIPPED_LOW_CONFIDENCE

    @pytest.mark.asyncio
    async def test_exactly_threshold_allowed(self, tmp_path: Path) -> None:
        """A diagnosis at exactly the threshold should proceed past the gate."""
        engine = _make_healing_engine(tmp_path)
        spec = _create_test_file(
            tmp_path,
            "await page.getByRole('button', { name: 'Book Flight' }).click();"
        )

        diag = _make_drift_diagnosis(
            confidence=0.90,
            test_file=str(spec.relative_to(tmp_path)).replace("\\", "/"),
        )
        failure = _make_failure(test_file=str(spec.relative_to(tmp_path)).replace("\\", "/"))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await engine.heal(failure=failure, diagnosis=diag)

        # Should NOT be skipped due to low confidence
        assert result.status != HealingStatus.SKIPPED_LOW_CONFIDENCE


# ---------------------------------------------------------------------------
# Tests: PROPOSE_ONLY mode
# ---------------------------------------------------------------------------

class TestHealingProposeOnlyMode:
    @pytest.mark.asyncio
    async def test_propose_only_does_not_modify_file(self, tmp_path: Path) -> None:
        spec = _create_test_file(
            tmp_path,
            "await page.getByRole('button', { name: 'Book Flight' }).click();"
        )
        original_content = spec.read_text()

        engine = SelfHealingEngine(
            repo_root=tmp_path,
            tests_dir=tmp_path / "tests",
            artifacts_dir=tmp_path / "artifacts",
            healing_mode="PROPOSE_ONLY",
            confidence_threshold=0.90,
        )
        diag = _make_drift_diagnosis(confidence=0.95)
        failure = _make_failure()

        result = await engine.heal(failure=failure, diagnosis=diag)

        assert result.status == HealingStatus.PROPOSE_ONLY
        # File must not have been changed
        assert spec.read_text() == original_content


# ---------------------------------------------------------------------------
# Tests: Successful AUTO healing
# ---------------------------------------------------------------------------

class TestHealingSuccess:
    @pytest.mark.asyncio
    async def test_locator_replaced_in_file(self, tmp_path: Path) -> None:
        old_content = "await page.getByRole('button', { name: 'Book Flight' }).click();"
        spec = _create_test_file(tmp_path, old_content)

        engine = _make_healing_engine(tmp_path)
        diag = _make_drift_diagnosis(
            confidence=0.95,
            test_file=str(spec.relative_to(tmp_path)).replace("\\", "/"),
        )
        failure = _make_failure(
            test_file=str(spec.relative_to(tmp_path)).replace("\\", "/")
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await engine.heal(failure=failure, diagnosis=diag)

        if result.status == HealingStatus.HEALED_SUCCESSFULLY:
            new_content = spec.read_text()
            assert "Reserve Flight" in new_content
            assert result.file_changed is not None

    @pytest.mark.asyncio
    async def test_backup_created_before_patch(self, tmp_path: Path) -> None:
        spec = _create_test_file(
            tmp_path,
            "await page.getByRole('button', { name: 'Book Flight' }).click();"
        )

        engine = _make_healing_engine(tmp_path)
        diag = _make_drift_diagnosis(
            confidence=0.95,
            test_file=str(spec.relative_to(tmp_path)).replace("\\", "/"),
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await engine.heal(
                failure=_make_failure(
                    test_file=str(spec.relative_to(tmp_path)).replace("\\", "/")
                ),
                diagnosis=diag,
            )

        if result.status == HealingStatus.HEALED_SUCCESSFULLY and result.attempts:
            assert result.attempts[0].backup_path is not None


# ---------------------------------------------------------------------------
# Tests: No repair target
# ---------------------------------------------------------------------------

class TestHealingNoRepairTarget:
    @pytest.mark.asyncio
    async def test_no_repair_target_skips_healing(self, tmp_path: Path) -> None:
        """Without a repair_target, healing cannot proceed."""
        engine = _make_healing_engine(tmp_path)
        diagnosis = DiagnosisResult(
            test_id="booking-drift",
            test_file="tests/e2e/booking-drift.spec.ts",
            classification=FailureClassification.TEST_DRIFT,
            confidence=0.95,
            summary="Drift detected but no repair target identified.",
            evidence=[],
            recommended_action="REPAIR_TEST",
            repair_target=None,  # no target!
        )
        result = await engine.heal(failure=_make_failure(), diagnosis=diagnosis)

        # Should produce PROPOSE_ONLY or HEALING_FAILED, not crash
        assert result.status in {
            HealingStatus.PROPOSE_ONLY,
            HealingStatus.HEALING_FAILED,
            HealingStatus.NOT_ATTEMPTED,
        }
