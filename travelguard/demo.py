"""Deterministic demo runner for hackathon presentations."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from travelguard.analyzer import ChangeImpactAnalyzer
from travelguard.change_detector import ChangeDetector, FixtureChangeSource
from travelguard.models import ChangeSet, ImpactAnalysisResult


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
}


def load_scenario_diff(scenario_key: str) -> str:
    """Load unified diff text for a demo scenario."""
    meta = DEMO_SCENARIOS.get(scenario_key)
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
    scenario = DEMO_SCENARIOS.get(scenario_key)
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
