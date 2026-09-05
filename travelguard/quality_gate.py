"""Quality Gate for TravelGuard AI release decisions and CI/CD gate enforcement.

Evaluates test results, failure classifications, and release confidence to decide
whether a commit or PR is safe for release:
  - PASS: Allow release (exit code 0)
  - PASS_WITH_HEALING: Allow release with audit warning (exit code 0)
  - REAL_DEFECT: Block release (exit code 2)
  - BLOCKED: Block release due to infra/environment (exit code 3)
  - UNKNOWN: Block release due to unclassified failure (exit code 4)
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from travelguard.models import QualityReport, QualityStatus
from travelguard.release_confidence import ReleaseConfidenceResult


class GateAction(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_AUDIT = "ALLOW_WITH_AUDIT"
    BLOCK = "BLOCK"


class QualityGateDecision(BaseModel):
    """Structured decision returned by the quality gate."""
    action: GateAction = Field(..., description="ALLOW | ALLOW_WITH_AUDIT | BLOCK")
    exit_code: int = Field(..., description="Process exit code for CI/CD pipeline")
    verdict: str = Field(..., description="Human readable quality verdict")
    reason: str = Field(..., description="Detailed explanation of the decision")
    confidence: float = Field(..., description="Release confidence score considered")
    passed_gate: bool = Field(..., description="True if release is permitted")


class QualityGate:
    """Configurable release quality gate."""

    def __init__(
        self,
        allow_healing: bool = True,
        min_confidence: float = 0.75,
        block_on_env_failure: bool = True,
    ):
        self.allow_healing = allow_healing
        self.min_confidence = min_confidence
        self.block_on_env_failure = block_on_env_failure

    def evaluate(
        self,
        quality_report: QualityReport,
        confidence_result: Optional[ReleaseConfidenceResult] = None,
    ) -> QualityGateDecision:
        status = quality_report.status
        confidence = (
            confidence_result.confidence
            if confidence_result
            else quality_report.release_confidence
        )

        # 1. Real Product Defect -> Always Block
        if status == QualityStatus.REAL_DEFECT or quality_report.real_defects > 0:
            return QualityGateDecision(
                action=GateAction.BLOCK,
                exit_code=2,
                verdict="RELEASE BLOCKED",
                reason=f"Real product defect(s) detected ({quality_report.real_defects}). Release halted to protect production.",
                confidence=confidence,
                passed_gate=False,
            )

        # 2. Unknown Failures -> Block (check before generic BLOCKED status)
        if quality_report.unknown_failures > 0:
            return QualityGateDecision(
                action=GateAction.BLOCK,
                exit_code=4,
                verdict="RELEASE BLOCKED (UNKNOWN FAILURE)",
                reason=f"Unclassified test failure(s) ({quality_report.unknown_failures}) require manual investigation.",
                confidence=confidence,
                passed_gate=False,
            )

        # 3. Environment / Infrastructure Failure -> Block
        if status == QualityStatus.BLOCKED or quality_report.environment_failures > 0:
            return QualityGateDecision(
                action=GateAction.BLOCK,
                exit_code=3,
                verdict="RELEASE BLOCKED (ENVIRONMENT FAILURE)",
                reason=f"Pipeline blocked by {quality_report.environment_failures} environment/infrastructure failure(s).",
                confidence=confidence,
                passed_gate=False,
            )

        # 4. Unknown Failures (unreachable guard kept for safety) - already handled above

        # 4. Standard failures after healing -> Block
        if status == QualityStatus.FAIL or quality_report.failed > 0:
            return QualityGateDecision(
                action=GateAction.BLOCK,
                exit_code=1,
                verdict="RELEASE BLOCKED (TEST FAILURES)",
                reason=f"{quality_report.failed} test(s) failed without successful automated repair.",
                confidence=confidence,
                passed_gate=False,
            )

        # 5. Confidence Gate check
        if confidence < self.min_confidence:
            return QualityGateDecision(
                action=GateAction.BLOCK,
                exit_code=1,
                verdict="RELEASE BLOCKED (LOW CONFIDENCE)",
                reason=f"Release confidence ({confidence:.0%}) is below required gate threshold ({self.min_confidence:.0%}).",
                confidence=confidence,
                passed_gate=False,
            )

        # 6. Self-Healed Pass
        if status == QualityStatus.PASS_WITH_HEALING or quality_report.healed > 0:
            if not self.allow_healing:
                return QualityGateDecision(
                    action=GateAction.BLOCK,
                    exit_code=1,
                    verdict="RELEASE BLOCKED (HEALING DISALLOWED)",
                    reason="Policy disallows automatic test healing for production release.",
                    confidence=confidence,
                    passed_gate=False,
                )
            return QualityGateDecision(
                action=GateAction.ALLOW_WITH_AUDIT,
                exit_code=0,
                verdict="RELEASE ALLOWED (PASS WITH HEALING)",
                reason=f"{quality_report.healed} test(s) successfully self-healed and re-verified. Audit record generated.",
                confidence=confidence,
                passed_gate=True,
            )

        # 7. Clean Pass
        return QualityGateDecision(
            action=GateAction.ALLOW,
            exit_code=0,
            verdict="RELEASE ALLOWED (CLEAN PASS)",
            reason=f"All {quality_report.selected_tests} selected tests passed cleanly with {confidence:.0%} confidence.",
            confidence=confidence,
            passed_gate=True,
        )
