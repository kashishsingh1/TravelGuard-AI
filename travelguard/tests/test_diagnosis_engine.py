"""Unit tests for FailureDiagnosisEngine.

All tests mock the LLM service — no live API calls required.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from travelguard.diagnosis_engine import (
    FailureDiagnosisEngine,
    _is_environment_failure,
    _extract_json_from_llm,
    _build_evidence_prompt,
)
from travelguard.models import (
    ChangeSet,
    ChangeSourceType,
    DiagnosisResult,
    FailureClassification,
    FileChange,
    TestFailureInfo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_failure(
    error_message: str = "Timeout 30000ms exceeded",
    stderr: str = "",
    locator_used: str = "getByRole('button', { name: 'Book Flight' })",
    test_id: str = "booking-drift",
) -> TestFailureInfo:
    return TestFailureInfo(
        test_id=test_id,
        test_name="Flight Booking Drift Detection",
        test_file="tests/e2e/booking-drift.spec.ts",
        error_message=error_message,
        stderr=stderr,
        locator_used=locator_used,
        duration_ms=1540,
    )


def _make_change_set(path: str = "frontend/src/PassengerForm.tsx", diff: str = "") -> ChangeSet:
    return ChangeSet(
        source=ChangeSourceType.FIXTURE,
        files=[
            FileChange(path=path, diff=diff, additions=3, deletions=2)
        ],
    )


def _make_llm_service(response_content: str) -> MagicMock:
    """Build a mock LLM service that returns the given string content."""
    mock_response = MagicMock()
    mock_response.content = response_content
    mock_response.provider = "groq"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_response)
    return mock_llm


# ---------------------------------------------------------------------------
# Unit: _is_environment_failure
# ---------------------------------------------------------------------------

class TestIsEnvironmentFailure:
    def test_econnrefused_detected(self) -> None:
        assert _is_environment_failure("connect ECONNREFUSED 127.0.0.1:3000", "") is True

    def test_err_connection_refused_detected(self) -> None:
        assert _is_environment_failure("net::ERR_CONNECTION_REFUSED", "") is True

    def test_browser_closed_detected(self) -> None:
        assert _is_environment_failure("Target page has been closed", "") is True

    def test_timeout_waiting_for_not_env_failure(self) -> None:
        """Timeout waiting for a locator is NOT an environment failure."""
        assert _is_environment_failure("Timeout waiting for getByRole", "") is False

    def test_getbyrole_not_env_failure(self) -> None:
        assert _is_environment_failure("getByRole('button') not found", "") is False

    def test_empty_strings_not_env_failure(self) -> None:
        assert _is_environment_failure("", "") is False


# ---------------------------------------------------------------------------
# Unit: _extract_json_from_llm
# ---------------------------------------------------------------------------

class TestExtractJsonFromLLM:
    def test_direct_json(self) -> None:
        raw = '{"classification": "TEST_DRIFT", "confidence": 0.95}'
        result = _extract_json_from_llm(raw)
        assert result["classification"] == "TEST_DRIFT"

    def test_json_in_markdown_fence(self) -> None:
        raw = '```json\n{"classification": "PRODUCT_DEFECT", "confidence": 0.85}\n```'
        result = _extract_json_from_llm(raw)
        assert result["classification"] == "PRODUCT_DEFECT"

    def test_json_with_surrounding_text(self) -> None:
        raw = 'Here is the analysis:\n{"classification": "UNKNOWN", "confidence": 0.4}\nEnd.'
        result = _extract_json_from_llm(raw)
        assert result["classification"] == "UNKNOWN"

    def test_trailing_comma_cleaned(self) -> None:
        raw = '{"classification": "TEST_DRIFT", "confidence": 0.9,}'
        result = _extract_json_from_llm(raw)
        assert result["confidence"] == 0.9

    def test_empty_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _extract_json_from_llm("")

    def test_unparseable_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _extract_json_from_llm("not json at all")


# ---------------------------------------------------------------------------
# Integration: FailureDiagnosisEngine.diagnose
# ---------------------------------------------------------------------------

class TestFailureDiagnosisEngineEnvironmentFastPath:
    @pytest.mark.asyncio
    async def test_econnrefused_skips_llm(self) -> None:
        """ECONNREFUSED should be classified without LLM call."""
        mock_llm = _make_llm_service("{}")  # should NOT be called

        engine = FailureDiagnosisEngine(llm_service=mock_llm)
        failure = _make_failure(error_message="FetchError: connect ECONNREFUSED 127.0.0.1:9999")
        change_set = _make_change_set()

        result = await engine.diagnose(failure=failure, change_set=change_set)

        assert result.classification == FailureClassification.ENVIRONMENT_FAILURE
        assert result.provider_used == "deterministic"
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_environment_failure_confidence_high(self) -> None:
        engine = FailureDiagnosisEngine(llm_service=MagicMock())
        failure = _make_failure(error_message="net::ERR_CONNECTION_REFUSED")
        result = await engine.diagnose(failure=failure, change_set=_make_change_set())

        assert result.confidence >= 0.95


class TestFailureDiagnosisEngineLLMPath:
    @pytest.mark.asyncio
    async def test_test_drift_classified_correctly(self) -> None:
        llm_json = """{
            "classification": "TEST_DRIFT",
            "confidence": 0.93,
            "summary": "Button label changed from Book Flight to Reserve Flight.",
            "evidence": ["UI diff shows button text change", "Locator references old label"],
            "business_behavior_changed": false,
            "recommended_action": "REPAIR_TEST",
            "repair_target": {
                "file": "tests/e2e/booking-drift.spec.ts",
                "line": 25,
                "old_locator": "getByRole('button', { name: 'Book Flight' })",
                "new_locator": "getByRole('button', { name: 'Reserve Flight' })"
            }
        }"""
        engine = FailureDiagnosisEngine(llm_service=_make_llm_service(llm_json))
        failure = _make_failure()
        change_set = _make_change_set(diff="- Book Flight\n+ Reserve Flight")

        result = await engine.diagnose(failure=failure, change_set=change_set)

        assert result.classification == FailureClassification.TEST_DRIFT
        assert result.confidence == pytest.approx(0.93)
        assert result.repair_target is not None
        assert "Reserve Flight" in result.repair_target.new_locator
        assert result.business_behavior_changed is False

    @pytest.mark.asyncio
    async def test_product_defect_classified_correctly(self) -> None:
        llm_json = """{
            "classification": "PRODUCT_DEFECT",
            "confidence": 0.97,
            "summary": "API returns 500 Internal Server Error for booking.",
            "evidence": ["HTTP 500 in error message", "Backend validation regression"],
            "business_behavior_changed": true,
            "recommended_action": "RAISE_BUG"
        }"""
        engine = FailureDiagnosisEngine(llm_service=_make_llm_service(llm_json))
        failure = _make_failure(
            error_message="Expected: 200\nReceived: 500\nHTTP 500 Internal Server Error",
            locator_used="",
        )
        result = await engine.diagnose(failure=failure, change_set=_make_change_set())

        assert result.classification == FailureClassification.PRODUCT_DEFECT
        assert result.recommended_action == "RAISE_BUG"
        assert result.business_behavior_changed is True

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_heuristic(self) -> None:
        """When LLM raises, heuristic fallback should be used."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        engine = FailureDiagnosisEngine(llm_service=mock_llm)
        failure = _make_failure(
            error_message="HTTP 500 Internal Server Error",
        )
        change_set = _make_change_set()

        result = await engine.diagnose(failure=failure, change_set=change_set)

        assert result.classification in {
            FailureClassification.PRODUCT_DEFECT,
            FailureClassification.TEST_DRIFT,
            FailureClassification.UNKNOWN,
        }
        assert result.provider_used == "heuristic"

    @pytest.mark.asyncio
    async def test_invalid_classification_falls_back_to_unknown(self) -> None:
        """An unrecognised classification value should become UNKNOWN."""
        llm_json = '{"classification": "BANANA", "confidence": 0.5, "summary": "test"}'
        engine = FailureDiagnosisEngine(llm_service=_make_llm_service(llm_json))
        failure = _make_failure()

        result = await engine.diagnose(failure=failure, change_set=_make_change_set())

        assert result.classification == FailureClassification.UNKNOWN

    @pytest.mark.asyncio
    async def test_confidence_clamped_to_range(self) -> None:
        """Confidence must stay within [0.0, 1.0] regardless of LLM output."""
        llm_json = '{"classification": "TEST_DRIFT", "confidence": 99.9, "summary": "x"}'
        engine = FailureDiagnosisEngine(llm_service=_make_llm_service(llm_json))

        result = await engine.diagnose(failure=_make_failure(), change_set=_make_change_set())

        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Unit: _build_evidence_prompt
# ---------------------------------------------------------------------------

class TestBuildEvidencePrompt:
    def test_includes_test_name(self) -> None:
        failure = _make_failure()
        change_set = _make_change_set()
        prompt = _build_evidence_prompt(failure, change_set)
        assert "booking-drift" in prompt

    def test_includes_error_message(self) -> None:
        failure = _make_failure(error_message="UNIQUE_ERROR_XYZ")
        prompt = _build_evidence_prompt(failure, _make_change_set())
        assert "UNIQUE_ERROR_XYZ" in prompt

    def test_includes_diff(self) -> None:
        prompt = _build_evidence_prompt(
            _make_failure(),
            _make_change_set(diff="- old line\n+ new line"),
        )
        assert "old line" in prompt or "new line" in prompt

    def test_diff_truncated_at_1500_chars(self) -> None:
        long_diff = "x" * 5000
        prompt = _build_evidence_prompt(_make_failure(), _make_change_set(diff=long_diff))
        assert "truncated" in prompt.lower()
