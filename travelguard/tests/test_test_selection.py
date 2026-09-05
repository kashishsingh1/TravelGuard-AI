"""Unit tests for test inventory and intelligent test selection engine."""

import pytest
from travelguard.models import (
    ChangeSet,
    FileChange,
    ImpactAnalysisResult,
    JourneyImpact,
    RiskAssessment,
    TestPriority,
)
from travelguard.test_inventory import get_test_inventory
from travelguard.test_selector import DeterministicTestSelector


def test_inventory_loading():
    """Verify test inventory loads existing Playwright tests with proper metadata."""
    inventory = get_test_inventory()
    tests = inventory.get_all()

    assert len(tests) >= 5
    test_ids = {t.id for t in tests}
    assert "flight-booking" in test_ids
    assert "booking-api" in test_ids
    assert "passenger-validation" in test_ids
    assert "flight-search" in test_ids

    booking_test = inventory.get_by_id("flight-booking")
    assert booking_test is not None
    assert booking_test.priority_tier == TestPriority.P0
    assert booking_test.criticality == "critical"
    assert "flight_booking" in booking_test.business_journeys


def test_deterministic_selector_booking_change():
    """Verify booking form change selects P0 booking tests and skips search."""
    selector = DeterministicTestSelector()

    changes = ChangeSet(files=[
        FileChange(path="frontend/src/components/PassengerForm.tsx", additions=10, deletions=2)
    ])
    impact = ImpactAnalysisResult(
        summary="Modified passenger form validation",
        change_type="ui",
        is_behavioral=True,
        affected_journeys=[
            JourneyImpact(
                journey_id="flight_booking",
                journey_name="Flight Booking & Confirmation",
                impact_level="high",
                capability="Passenger details capture",
            )
        ],
        risk=RiskAssessment(level="high", score=80, reason="Form validation altered"),
        recommended_tests=[],
        business_impact="Failed customer checkout",
    )

    selected, skipped = selector.select(changes, impact)

    selected_ids = {s.test_id for s in selected}
    skipped_ids = {s.test_id for s in skipped}

    assert "flight-booking" in selected_ids
    assert "passenger-validation" in selected_ids
    assert "flight-search" in skipped_ids

    # Check P0 priority on flight-booking
    booking_sel = next(s for s in selected if s.test_id == "flight-booking")
    assert booking_sel.priority == TestPriority.P0
    assert len(booking_sel.reason) > 10


def test_deterministic_selector_cosmetic_change():
    """Verify cosmetic search button change selects search test as P2 and skips booking."""
    selector = DeterministicTestSelector()

    changes = ChangeSet(files=[
        FileChange(path="frontend/src/components/SearchForm.tsx", additions=1, deletions=1)
    ])
    impact = ImpactAnalysisResult(
        summary="Search button styling tweak",
        change_type="cosmetic",
        is_behavioral=False,
        affected_journeys=[
            JourneyImpact(
                journey_id="flight_search",
                journey_name="Flight Search",
                impact_level="low",
                capability="Search button presentation",
            )
        ],
        risk=RiskAssessment(level="low", score=15, reason="Cosmetic styling change"),
        recommended_tests=[],
        business_impact="None",
    )

    selected, skipped = selector.select(changes, impact)

    selected_ids = {s.test_id for s in selected}
    assert "flight-search" in selected_ids
    search_sel = next(s for s in selected if s.test_id == "flight-search")
    assert search_sel.priority == TestPriority.P2
