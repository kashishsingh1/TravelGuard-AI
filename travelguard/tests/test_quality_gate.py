"""Unit tests for QualityGate decisions and exit codes in TravelGuard AI."""

import pytest
from travelguard.models import QualityReport, QualityStatus
from travelguard.quality_gate import GateAction, QualityGate, QualityGateDecision
from travelguard.release_confidence import ReleaseConfidenceBreakdown, ReleaseConfidenceResult


def _make_report(
    status: QualityStatus,
    passed: int = 1,
    failed: int = 0,
    healed: int = 0,
    defects: int = 0,
    env_failures: int = 0,
    unknown: int = 0,
    confidence: float = 0.95,
) -> QualityReport:
    return QualityReport(
        run_id="test-run",
        timestamp="2026-09-05T00:00:00Z",
        status=status,
        changed_files=1,
        selected_tests=passed + failed + healed + defects + env_failures + unknown,
        skipped_tests=2,
        passed=passed,
        failed=failed,
        healed=healed,
        real_defects=defects,
        environment_failures=env_failures,
        unknown_failures=unknown,
        release_confidence=confidence,
        summary="Test summary",
    )


class TestQualityGate:
    """Validate release gate enforcement policies."""

    def test_clean_pass_allows_release(self):
        gate = QualityGate()
        report = _make_report(status=QualityStatus.PASS, passed=5, confidence=0.98)
        decision = gate.evaluate(report)
        assert decision.action == GateAction.ALLOW
        assert decision.exit_code == 0
        assert decision.passed_gate is True

    def test_healed_test_allows_with_audit(self):
        gate = QualityGate(allow_healing=True)
        report = _make_report(status=QualityStatus.PASS_WITH_HEALING, passed=2, healed=1, confidence=0.95)
        decision = gate.evaluate(report)
        assert decision.action == GateAction.ALLOW_WITH_AUDIT
        assert decision.exit_code == 0
        assert decision.passed_gate is True
        assert "PASS WITH HEALING" in decision.verdict

    def test_real_defect_blocks_release(self):
        gate = QualityGate()
        report = _make_report(status=QualityStatus.REAL_DEFECT, defects=1, confidence=0.0)
        decision = gate.evaluate(report)
        assert decision.action == GateAction.BLOCK
        assert decision.exit_code == 2
        assert decision.passed_gate is False
        assert "RELEASE BLOCKED" in decision.verdict

    def test_environment_failure_blocks_release(self):
        gate = QualityGate()
        report = _make_report(status=QualityStatus.BLOCKED, env_failures=1, confidence=0.3)
        decision = gate.evaluate(report)
        assert decision.action == GateAction.BLOCK
        assert decision.exit_code == 3
        assert decision.passed_gate is False
        assert "ENVIRONMENT FAILURE" in decision.verdict

    def test_unknown_failure_blocks_release(self):
        gate = QualityGate()
        report = _make_report(status=QualityStatus.BLOCKED, unknown=1, confidence=0.5)
        decision = gate.evaluate(report)
        assert decision.action == GateAction.BLOCK
        assert decision.exit_code == 4
        assert decision.passed_gate is False

    def test_low_confidence_blocks_release(self):
        gate = QualityGate(min_confidence=0.85)
        report = _make_report(status=QualityStatus.PASS, passed=2, confidence=0.70)
        decision = gate.evaluate(report)
        assert decision.action == GateAction.BLOCK
        assert decision.exit_code == 1
        assert decision.passed_gate is False
        assert "LOW CONFIDENCE" in decision.verdict
