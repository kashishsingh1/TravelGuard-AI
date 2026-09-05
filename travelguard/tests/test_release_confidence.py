from travelguard.models import DiagnosisResult, FailureClassification, JourneyCriticality, TestPriority, SelectedTest
from travelguard.release_confidence import ReleaseConfidenceEngine


def _make_test(name: str, tier: TestPriority = TestPriority.P1, criticality: str = "high") -> SelectedTest:
    return SelectedTest(
        test_id=name,
        name=name,
        file=f"tests/e2e/{name}.spec.ts",
        priority=tier,
        reason="Test selection reason",
    )


class TestReleaseConfidenceEngine:
    """Validate mathematical release confidence scoring."""

    def test_real_defect_instantly_zeros_confidence(self):
        tests = [_make_test("t1"), _make_test("t2")]
        diagnoses = [
            DiagnosisResult(
                test_id="t1",
                test_file="tests/e2e/t1.spec.ts",
                classification=FailureClassification.PRODUCT_DEFECT,
                confidence=0.98,
                summary="500 Internal Error",
            )
        ]
        result = ReleaseConfidenceEngine.compute(tests, passed_count=1, healed_count=0, diagnoses=diagnoses)
        assert result.confidence == 0.0
        assert result.release_decision == "REAL_DEFECT"
        assert result.breakdown.real_defect_penalty == 1.0

    def test_environment_failure_caps_at_30_percent(self):
        tests = [_make_test("t1")]
        diagnoses = [
            DiagnosisResult(
                test_id="t1",
                test_file="tests/e2e/t1.spec.ts",
                classification=FailureClassification.ENVIRONMENT_FAILURE,
                confidence=0.99,
                summary="Connection refused",
            )
        ]
        result = ReleaseConfidenceEngine.compute(tests, passed_count=0, healed_count=0, diagnoses=diagnoses)
        assert result.confidence <= 0.30
        assert result.release_decision == "BLOCKED"

    def test_all_passed_gives_full_confidence(self):
        tests = [_make_test("t1"), _make_test("t2")]
        result = ReleaseConfidenceEngine.compute(tests, passed_count=2, healed_count=0, diagnoses=[])
        assert result.confidence == 1.0
        assert result.release_decision == "PASS"

    def test_healed_test_has_5_percent_discount(self):
        tests = [_make_test("t1")]
        diagnoses = [
            DiagnosisResult(
                test_id="t1",
                test_file="tests/e2e/t1.spec.ts",
                classification=FailureClassification.TEST_DRIFT,
                confidence=0.95,
                summary="Locator changed",
            )
        ]
        result = ReleaseConfidenceEngine.compute(tests, passed_count=0, healed_count=1, diagnoses=diagnoses)
        assert result.confidence == 0.95
        assert result.release_decision == "PASS_WITH_HEALING"

    def test_unknown_penalizes_confidence(self):
        tests = [_make_test("t1"), _make_test("t2")]
        diagnoses = [
            DiagnosisResult(
                test_id="t1",
                test_file="tests/e2e/t1.spec.ts",
                classification=FailureClassification.UNKNOWN,
                confidence=0.5,
                summary="Unknown",
            )
        ]
        result = ReleaseConfidenceEngine.compute(tests, passed_count=1, healed_count=0, diagnoses=diagnoses)
        assert result.confidence < 0.50
        assert result.release_decision == "BLOCKED"
