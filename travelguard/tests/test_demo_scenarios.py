"""Unit tests for deterministic hackathon demo scenarios."""

import pytest
from travelguard.demo import DEMO_SCENARIOS, run_demo_scenario


@pytest.mark.asyncio
async def test_demo_scenario_a_cosmetic_ui():
    """Verify Scenario A: Cosmetic UI change on flight search form."""
    change_set, result = await run_demo_scenario("scenario_a", use_mock_llm=True)

    assert len(change_set.files) == 1
    assert "SearchForm.tsx" in change_set.files[0].path
    assert result.change_type == "cosmetic"
    assert result.is_behavioral is False
    assert result.risk.level == "low"
    assert result.risk.score <= 30
    assert any(j.journey_id == "flight_search" for j in result.affected_journeys)


@pytest.mark.asyncio
async def test_demo_scenario_b_booking_ui():
    """Verify Scenario B: Behavioral booking UI change on PassengerForm."""
    change_set, result = await run_demo_scenario("scenario_b", use_mock_llm=True)

    assert len(change_set.files) == 1
    assert "PassengerForm.tsx" in change_set.files[0].path
    assert result.change_type == "ui"
    assert result.is_behavioral is True
    assert result.risk.level == "high"
    assert result.risk.score >= 71
    assert any(j.journey_id == "flight_booking" for j in result.affected_journeys)
    # Check recommended tests include booking E2E
    assert any("booking.spec.ts" in t or "booking" in t.lower() for t in result.recommended_tests)


@pytest.mark.asyncio
async def test_demo_scenario_c_booking_api():
    """Verify Scenario C: Behavioral booking API change in backend."""
    change_set, result = await run_demo_scenario("scenario_c", use_mock_llm=True)

    assert len(change_set.files) == 1
    assert "booking.py" in change_set.files[0].path
    assert result.change_type == "api"
    assert result.is_behavioral is True
    assert result.risk.level == "critical"
    assert result.risk.score >= 91
    assert any(j.journey_id == "flight_booking" for j in result.affected_journeys)
    # Check recommended tests include booking API and booking E2E
    assert any("test_booking_success" in t or "booking" in t.lower() for t in result.recommended_tests)


@pytest.mark.asyncio
async def test_demo_scenario_d_promo_code():
    """Verify Scenario D: New Feature (Promo Code) change in PassengerForm."""
    change_set, result = await run_demo_scenario("scenario_d", use_mock_llm=True)

    assert len(change_set.files) == 1
    assert "PassengerForm.tsx" in change_set.files[0].path
    assert result.change_type == "ui"
    assert result.is_behavioral is True
    assert result.risk.level == "high"
    assert result.risk.score >= 70
    assert any(j.journey_id == "flight_booking" for j in result.affected_journeys)


def test_demo_scenarios_registry_completeness():
    """Verify all 4 required hackathon scenarios exist in registry."""
    assert "scenario_a" in DEMO_SCENARIOS
    assert "scenario_b" in DEMO_SCENARIOS
    assert "scenario_c" in DEMO_SCENARIOS
    assert "scenario_d" in DEMO_SCENARIOS
