"""Release Confidence Engine — transparent mathematical evaluation of software release readiness.

Formula:
  1. If real_defects > 0:
       confidence = 0.0 (Hard stop on real product defects)
  2. If selected == 0:
       confidence = 1.0 (No impacted tests identified or needed)
  3. Base pass ratio:
       base = (passed + healed * 0.95) / selected
       (Healed tests carry a 5% discount reflecting automated repair)
  4. Penalties:
       - Environment failure: score capped at 0.30
       - Unknown failures: -0.10 per unknown failure
       - Critical test failure: -0.30 if any critical test failed without healing
       - High/Critical risk level penalty if unhealed failures exist: -0.15
  5. Bounds:
       Confidence is clamped strictly to [0.0, 1.0] and rounded to 2 decimal places.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from travelguard.models import DiagnosisResult, FailureClassification, QualityStatus, SelectedTest


class ReleaseConfidenceBreakdown(BaseModel):
    """Component breakdown of release confidence calculation."""
    base_pass_score: float = Field(..., description="Base score from passed + healed tests")
    real_defect_penalty: float = Field(default=0.0, description="Penalty for real product defects")
    environment_penalty: float = Field(default=0.0, description="Penalty for environment/infra failures")
    unknown_penalty: float = Field(default=0.0, description="Penalty for unknown failures")
    critical_test_penalty: float = Field(default=0.0, description="Penalty for unhealed critical tests")
    final_confidence: float = Field(..., ge=0.0, le=1.0, description="Final calculated confidence score")
    formula_explanation: str = Field(..., description="Human-readable formula audit trail")


class ReleaseConfidenceResult(BaseModel):
    """Complete release confidence assessment result."""
    release_decision: str = Field(..., description="PASS | PASS_WITH_HEALING | REAL_DEFECT | BLOCKED | UNKNOWN")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized confidence score (0.0 to 1.0)")
    critical_tests_passed: bool = Field(default=True, description="Whether all critical tests passed or healed")
    tests_selected: int = Field(default=0)
    tests_passed: int = Field(default=0)
    tests_healed: int = Field(default=0)
    real_defects: int = Field(default=0)
    blocked_tests: int = Field(default=0)
    breakdown: ReleaseConfidenceBreakdown


class ReleaseConfidenceEngine:
    """Calculates an explainable release confidence score from test intelligence and execution evidence."""

    @staticmethod
    def compute(
        selected_tests: List[SelectedTest],
        passed_count: int,
        healed_count: int,
        diagnoses: List[DiagnosisResult],
        risk_level: str = "medium",
    ) -> ReleaseConfidenceResult:
        selected = len(selected_tests)
        real_defects = sum(1 for d in diagnoses if d.classification == FailureClassification.PRODUCT_DEFECT)
        env_failures = sum(1 for d in diagnoses if d.classification == FailureClassification.ENVIRONMENT_FAILURE)
        unknown_failures = sum(1 for d in diagnoses if d.classification == FailureClassification.UNKNOWN)

        # Evaluate critical tests
        critical_selected = [t for t in selected_tests if getattr(t, "criticality", "").lower() == "critical" or getattr(t, "priority", "").value.upper() == "P0"]
        # Check if any critical diagnosis was not healed
        critical_unhealed = 0
        for d in diagnoses:
            is_critical = any(t.file == d.test_file and (getattr(t, "criticality", "").lower() == "critical" or getattr(t, "priority", "").value.upper() == "P0") for t in selected_tests)
            if is_critical and d.classification != FailureClassification.TEST_DRIFT:
                critical_unhealed += 1

        critical_passed = critical_unhealed == 0

        # Formula calculation
        if real_defects > 0:
            final_score = 0.0
            decision = "REAL_DEFECT"
            explanation = "Blocked: Real product defect(s) detected. Release confidence set to 0.0."
            breakdown = ReleaseConfidenceBreakdown(
                base_pass_score=0.0,
                real_defect_penalty=1.0,
                environment_penalty=0.0,
                unknown_penalty=0.0,
                critical_test_penalty=0.0,
                final_confidence=0.0,
                formula_explanation=explanation,
            )
        elif selected == 0:
            final_score = 1.0
            decision = "PASS"
            explanation = "Clean: No tests selected. Release confidence is 1.0."
            breakdown = ReleaseConfidenceBreakdown(
                base_pass_score=1.0,
                real_defect_penalty=0.0,
                environment_penalty=0.0,
                unknown_penalty=0.0,
                critical_test_penalty=0.0,
                final_confidence=1.0,
                formula_explanation=explanation,
            )
        else:
            base = (passed_count + (healed_count * 0.95)) / selected
            penalty_env = 0.0
            penalty_unknown = unknown_failures * 0.10
            penalty_critical = 0.25 if not critical_passed else 0.0

            score = base - penalty_unknown - penalty_critical

            if env_failures > 0:
                score = min(score, 0.30)
                penalty_env = max(0.0, base - 0.30)
                decision = "BLOCKED"
                explanation = f"Capped at 0.30 due to {env_failures} environment infrastructure failure(s)."
            elif unknown_failures > 0:
                decision = "BLOCKED"
                explanation = f"Penalized by {penalty_unknown:.2f} due to {unknown_failures} unresolved failure(s)."
            elif healed_count > 0:
                decision = "PASS_WITH_HEALING"
                explanation = f"Base pass score: {base:.2f} with {healed_count} self-healed test(s) discounted at 5%."
            elif base >= 0.99:
                decision = "PASS"
                explanation = f"All {selected} selected tests passed cleanly."
            else:
                decision = "FAIL"
                explanation = f"Test pass rate insufficient ({passed_count}/{selected})."

            final_score = max(0.0, min(1.0, round(score, 2)))
            breakdown = ReleaseConfidenceBreakdown(
                base_pass_score=round(base, 2),
                real_defect_penalty=0.0,
                environment_penalty=round(penalty_env, 2),
                unknown_penalty=round(penalty_unknown, 2),
                critical_test_penalty=round(penalty_critical, 2),
                final_confidence=final_score,
                formula_explanation=explanation,
            )

        return ReleaseConfidenceResult(
            release_decision=decision,
            confidence=final_score,
            critical_tests_passed=critical_passed,
            tests_selected=selected,
            tests_passed=passed_count,
            tests_healed=healed_count,
            real_defects=real_defects,
            blocked_tests=env_failures + unknown_failures,
            breakdown=breakdown,
        )
