"""Deterministic demo runner for hackathon presentations."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from travelguard.analyzer import ChangeImpactAnalyzer
from travelguard.change_detector import ChangeDetector, FixtureChangeSource
from travelguard.models import ChangeSet, ImpactAnalysisResult, SelectedTest, TestPriority


FIXTURES_DIR = Path(__file__).parent / "fixtures"


DEMO_SCENARIOS = {
    "scenario_a": {
        "id": "scenario_a",
        "name": "Scenario A: Cosmetic UI Change",
        "description": "Button styling and label change on Flight Search form",
        "fixture_file": "scenario_a_cosmetic_ui.diff",
        "mock_response": {
            "summary": "Updated search button styling classes and text label",
            "change_type": "cosmetic",
            "is_behavioral": False,
            "affected_journeys": [
                {
                    "journey_id": "flight_search",
                    "journey_name": "Flight Search",
                    "impact_level": "low",
                    "capability": "Flight search form button visual presentation",
                }
            ],
            "ai_risk_level": "low",
            "ai_risk_reason": "Purely cosmetic styling change to search button; no API or state logic altered.",
            "recommended_tests": [
                "Flight Search E2E (tests/e2e/search.spec.ts)",
            ],
            "business_impact": "Negligible risk to flight discovery workflow.",
            "confidence": 0.98,
        },
    },
    "scenario_b": {
        "id": "scenario_b",
        "name": "Scenario B: Booking UI Change",
        "description": "Submission handler and validation logic modification in PassengerForm",
        "fixture_file": "scenario_b_booking_ui.diff",
        "mock_response": {
            "summary": "Modified form submission handler and payload construction in PassengerForm",
            "change_type": "ui",
            "is_behavioral": True,
            "affected_journeys": [
                {
                    "journey_id": "flight_booking",
                    "journey_name": "Flight Booking & Confirmation",
                    "impact_level": "high",
                    "capability": "Passenger details capture and booking initiation",
                }
            ],
            "ai_risk_level": "high",
            "ai_risk_reason": "Alters form submission pipeline and passenger payload prior to booking dispatch.",
            "recommended_tests": [
                "Flight Booking E2E (tests/e2e/booking.spec.ts)",
                "Booking Creation API (backend/tests/test_api.py::test_booking_success)",
            ],
            "business_impact": "Potential breakage in customer checkout and flight booking completion.",
            "confidence": 0.95,
        },
    },
    "scenario_c": {
        "id": "scenario_c",
        "name": "Scenario C: Booking API Change",
        "description": "Server validation and booking ID format altered in /api/book",
        "fixture_file": "scenario_c_booking_api.diff",
        "mock_response": {
            "summary": "Changed passenger name validation criteria and booking ID format in booking API",
            "change_type": "api",
            "is_behavioral": True,
            "affected_journeys": [
                {
                    "journey_id": "flight_booking",
                    "journey_name": "Flight Booking & Confirmation",
                    "impact_level": "critical",
                    "capability": "Server-side booking creation and reservation confirmation",
                }
            ],
            "ai_risk_level": "critical",
            "ai_risk_reason": "Direct alteration of backend booking contract and passenger validation logic.",
            "recommended_tests": [
                "Booking Creation API (backend/tests/test_api.py::test_booking_success)",
                "Booking Validation API (backend/tests/test_api.py::test_booking_validation_failure)",
                "Flight Booking E2E (tests/e2e/booking.spec.ts)",
            ],
            "business_impact": "Direct risk of booking transaction failures, 400 errors, or downstream booking mismatch.",
            "confidence": 0.97,
        },
    },
    "scenario_d": {
        "id": "scenario_d",
        "name": "Scenario D: New Feature (Promo Code)",
        "description": "Promotional discount coupon input and dynamic calculation added to PassengerForm",
        "fixture_file": "scenario_d_promo_code.diff",
        "mock_response": {
            "summary": "Added promotional discount coupon input and discount calculation to passenger details checkout",
            "change_type": "ui",
            "is_behavioral": True,
            "affected_journeys": [
                {
                    "journey_id": "flight_booking",
                    "journey_name": "Flight Booking & Confirmation",
                    "impact_level": "high",
                    "capability": "Promotional coupon application and checkout fare calculation",
                }
            ],
            "ai_risk_level": "high",
            "ai_risk_reason": "Introduces new promotional code state, coupon validation, and dynamic fare modification.",
            "recommended_tests": [
                "Flight Booking E2E (tests/e2e/booking.spec.ts)",
                "Booking Creation API (backend/tests/test_api.py::test_booking_success)",
            ],
            "business_impact": "Pricing discrepancy or checkout disruption if promotional calculation fails.",
            "confidence": 0.96,
        },
    },
    "booking-ui-drift": {
        "id": "booking-ui-drift",
        "name": "Scenario: Booking UI Drift (Self-Healing)",
        "description": "Button locator drifted from 'Book Flight' to 'Reserve Flight' in PassengerForm",
        "fixture_file": "booking_ui_drift.diff",
        "mock_response": {
            "summary": "Button label and testid changed to Reserve Flight in PassengerForm",
            "change_type": "ui",
            "is_behavioral": True,
            "affected_journeys": [
                {
                    "journey_id": "flight_booking",
                    "journey_name": "Flight Booking & Confirmation",
                    "impact_level": "high",
                    "capability": "Flight booking submission button",
                }
            ],
            "ai_risk_level": "medium",
            "ai_risk_reason": "Button text and locator changed, causing drift in existing Playwright tests.",
            "recommended_tests": [
                "Flight Booking Drift Detection (tests/e2e/booking-drift.spec.ts)",
            ],
            "business_impact": "Booking workflow intact; automated test locator drifted.",
            "confidence": 0.95,
        },
        "expected_classification": "TEST_DRIFT",
    },
    "booking-api-defect": {
        "id": "booking-api-defect",
        "name": "Scenario: Booking API Defect (Real Regression)",
        "description": "Backend API introduces faulty name casing constraint causing HTTP 500",
        "fixture_file": "booking_api_defect.diff",
        "mock_response": {
            "summary": "Backend validation raises 500 for non-uppercase passenger names",
            "change_type": "api",
            "is_behavioral": True,
            "affected_journeys": [
                {
                    "journey_id": "flight_booking",
                    "journey_name": "Flight Booking & Confirmation",
                    "impact_level": "critical",
                    "capability": "Server-side booking creation API",
                }
            ],
            "ai_risk_level": "critical",
            "ai_risk_reason": "Severe regression: server-side 500 error when booking flights with standard names.",
            "recommended_tests": [
                "API Health & Booking Contract (tests/e2e/api-health.spec.ts)",
                "End-to-End Flight Booking (tests/e2e/booking.spec.ts)",
            ],
            "business_impact": "Complete booking service disruption for end-users.",
            "confidence": 0.99,
        },
        "expected_classification": "PRODUCT_DEFECT",
    },
    "environment-failure": {
        "id": "environment-failure",
        "name": "Scenario: Environment Infrastructure Failure",
        "description": "Frontend configured to unreachable port 9999 causing connection refused",
        "fixture_file": "environment_failure.diff",
        "mock_response": {
            "summary": "API endpoint points to inactive port 9999 causing ERR_CONNECTION_REFUSED",
            "change_type": "config",
            "is_behavioral": True,
            "affected_journeys": [
                {
                    "journey_id": "flight_search",
                    "journey_name": "Flight Search",
                    "impact_level": "critical",
                    "capability": "Backend API communication link",
                }
            ],
            "ai_risk_level": "critical",
            "ai_risk_reason": "Total loss of API connectivity due to port misconfiguration.",
            "recommended_tests": [
                "API Health & Booking Contract (tests/e2e/api-health.spec.ts)",
            ],
            "business_impact": "Frontend cannot reach any backend endpoints.",
            "confidence": 0.99,
        },
        "expected_classification": "ENVIRONMENT_FAILURE",
    },
}

# Add underscore aliases
DEMO_SCENARIOS["booking_ui_drift"] = DEMO_SCENARIOS["booking-ui-drift"]
DEMO_SCENARIOS["booking_api_defect"] = DEMO_SCENARIOS["booking-api-defect"]
DEMO_SCENARIOS["environment_failure"] = DEMO_SCENARIOS["environment-failure"]


def load_scenario_diff(scenario_key: str) -> str:
    """Load unified diff text for a demo scenario."""
    norm_key = scenario_key.replace("_", "-")
    meta = DEMO_SCENARIOS.get(scenario_key) or DEMO_SCENARIOS.get(norm_key)
    if not meta:
        raise ValueError(f"Unknown scenario '{scenario_key}'. Choose from: {list(DEMO_SCENARIOS.keys())}")
    diff_path = FIXTURES_DIR / meta["fixture_file"]
    return diff_path.read_text(encoding="utf-8")


async def run_demo_scenario(
    scenario_key: str,
    use_mock_llm: bool = False,
    analyzer: Optional[ChangeImpactAnalyzer] = None,
) -> Tuple[ChangeSet, ImpactAnalysisResult]:
    """Execute analysis for a specific demo scenario without modifying any repository files."""
    norm_key = scenario_key.replace("_", "-")
    scenario = DEMO_SCENARIOS.get(scenario_key) or DEMO_SCENARIOS.get(norm_key)
    if not scenario:
        raise ValueError(f"Invalid demo scenario: {scenario_key}")

    raw_diff = load_scenario_diff(scenario_key)
    source = FixtureChangeSource(raw_diff=raw_diff, fixture_name=scenario["name"])
    detector = ChangeDetector(source=source)
    change_set = detector.get_change_set()

    analyzer = analyzer or ChangeImpactAnalyzer()
    mock_payload = scenario["mock_response"] if use_mock_llm else None

    result = await analyzer.analyze(change_set=change_set, mock_response=mock_payload)
    return change_set, result


def create_demo_execution_results(scenario_key: str) -> Optional[List[Any]]:
    """Create deterministic simulated test execution results for autonomous demo runs."""
    from travelguard.models import TestExecutionResult, TestFailureInfo

    norm_key = scenario_key.replace("_", "-")
    if norm_key == "booking-ui-drift":
        failure = TestFailureInfo(
            test_id="booking-drift",
            test_name="TEST: Flight Booking Drift Detection",
            test_file="tests/e2e/booking-drift.spec.ts",
            error_message="Error: locator.click: Target closed\n=========================== logs ===========================\nwaiting for getByRole('button', { name: 'Book Flight' })\n============================================================",
            stack_trace="Error: locator.click: Target closed\n    at tests/e2e/booking-drift.spec.ts:25:56",
            failure_line=25,
            locator_used="getByRole('button', { name: 'Book Flight' })",
            test_source_snippet="  24    // 5. Submit booking using getByRole locator\n  25 >>> await page.getByRole('button', { name: 'Book Flight' }).click();\n  26    ",
            duration_ms=1540,
        )
        return [
            TestExecutionResult(
                test_id="booking-drift",
                test_file="tests/e2e/booking-drift.spec.ts",
                test_name="TEST: Flight Booking Drift Detection",
                status="failed",
                failure=failure,
                duration_ms=1540,
            )
        ]

    if norm_key == "booking-api-defect":
        failure = TestFailureInfo(
            test_id="booking-api",
            test_name="API Health & Booking Contract",
            test_file="tests/e2e/api-health.spec.ts",
            error_message="Error: expect(received).toBe(expected)\n\nExpected: 200\nReceived: 500\n\nHTTP 500 Internal Server Error: Passenger name must be uppercase",
            stack_trace="Error: expect(received).toBe(expected)\n    at tests/e2e/api-health.spec.ts:42:28",
            failure_line=42,
            expected_value="200",
            actual_value="500",
            duration_ms=480,
        )
        return [
            TestExecutionResult(
                test_id="booking-api",
                test_file="tests/e2e/api-health.spec.ts",
                test_name="API Health & Booking Contract",
                status="failed",
                failure=failure,
                duration_ms=480,
            )
        ]

    if norm_key == "environment-failure":
        failure = TestFailureInfo(
            test_id="booking-api",
            test_name="API Health & Booking Contract",
            test_file="tests/e2e/api-health.spec.ts",
            error_message="FetchError: connect ECONNREFUSED 127.0.0.1:9999\nERR_CONNECTION_REFUSED",
            stack_trace="FetchError: connect ECONNREFUSED 127.0.0.1:9999\n    at tests/e2e/api-health.spec.ts:18:14",
            failure_line=18,
            duration_ms=120,
        )
        return [
            TestExecutionResult(
                test_id="booking-api",
                test_file="tests/e2e/api-health.spec.ts",
                test_name="API Health & Booking Contract",
                status="failed",
                failure=failure,
                duration_ms=120,
            )
        ]

    return None


def create_demo_selected_tests(scenario_key: str) -> Optional[List[SelectedTest]]:
    """Return a deterministic list of SelectedTest for a demo scenario.

    This bypasses the LLM test selector entirely so that autonomous-demo
    always runs the exact same tests regardless of LLM availability or
    non-determinism.
    """
    norm_key = scenario_key.replace("_", "-")

    if norm_key == "booking-ui-drift":
        return [
            SelectedTest(
                test_id="booking-drift",
                file="tests/e2e/booking-drift.spec.ts",
                name="Flight Booking Drift Detection",
                priority=TestPriority.P1,
                reason="Booking button locator drifted from 'Book Flight' to 'Reserve Flight'; this test exercises that locator directly.",
                confidence=0.99,
            ),
        ]

    if norm_key == "booking-api-defect":
        return [
            SelectedTest(
                test_id="booking-api",
                file="tests/e2e/api-health.spec.ts",
                name="API Health & Booking Contract",
                priority=TestPriority.P0,
                reason="Booking API validation regression; this test exercises the POST /api/book endpoint directly.",
                confidence=0.99,
            ),
            SelectedTest(
                test_id="flight-booking",
                file="tests/e2e/booking.spec.ts",
                name="End-to-End Flight Booking",
                priority=TestPriority.P0,
                reason="Backend 500 during booking checkout; end-to-end booking flow must fail with real defect verdict.",
                confidence=0.99,
            ),
        ]

    if norm_key == "environment-failure":
        return [
            SelectedTest(
                test_id="booking-api",
                file="tests/e2e/api-health.spec.ts",
                name="API Health & Booking Contract",
                priority=TestPriority.P0,
                reason="Frontend misconfigured to unreachable port; API health check will fail with ERR_CONNECTION_REFUSED.",
                confidence=0.99,
            ),
        ]

    # For older analysis-only scenarios, no pre-built selection needed
    return None


class DemoSUTContext:
    """
    Context manager that synchronizes the live System Under Test (SUT) with demo scenario changes.
    Temporarily applies real application code changes on disk so that Vite HMR serves the
    updated UI to the browser during the live autonomous run, and guarantees clean restoration
    afterwards.
    """

    def __init__(self, scenario_key: str, repo_root: Optional[Path] = None):
        norm_key = scenario_key.replace("_", "-")
        self.scenario_key = norm_key
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent
        self.passenger_form_path = self.repo_root / "frontend" / "src" / "components" / "PassengerForm.tsx"
        self.test_spec_path = self.repo_root / "tests" / "e2e" / "booking-drift.spec.ts"
        self._orig_passenger_form: Optional[str] = None
        self._orig_test_spec: Optional[str] = None

    def __enter__(self):
        import time
        if self.scenario_key == "booking-ui-drift":
            if self.passenger_form_path.exists():
                self._orig_passenger_form = self.passenger_form_path.read_text(encoding="utf-8")
                # Apply the real UI change: Book Flight -> Reserve Flight
                updated = self._orig_passenger_form.replace(
                    'data-testid="book-flight"', 'data-testid="reserve-flight"'
                ).replace(
                    "{isLoading ? 'Processing Booking...' : 'Book Flight'}",
                    "{isLoading ? 'Processing Booking...' : 'Reserve Flight'}",
                )
                self.passenger_form_path.write_text(updated, encoding="utf-8")
                # Allow Vite dev server HMR to propagate update
                time.sleep(1.0)
            if self.test_spec_path.exists():
                self._orig_test_spec = self.test_spec_path.read_text(encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        # Always restore files to original pristine state
        if self._orig_passenger_form is not None and self.passenger_form_path.exists():
            self.passenger_form_path.write_text(self._orig_passenger_form, encoding="utf-8")
            time.sleep(0.5)
        if self._orig_test_spec is not None and self.test_spec_path.exists():
            self.test_spec_path.write_text(self._orig_test_spec, encoding="utf-8")
            time.sleep(0.2)


