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
    """Verify all required hackathon scenarios exist in registry."""
    assert "scenario_a" in DEMO_SCENARIOS
    assert "scenario_b" in DEMO_SCENARIOS
    assert "scenario_c" in DEMO_SCENARIOS
    assert "scenario_d" in DEMO_SCENARIOS
    assert "booking-ui-drift" in DEMO_SCENARIOS
    assert "booking-api-defect" in DEMO_SCENARIOS
    assert "environment-failure" in DEMO_SCENARIOS


def test_create_demo_selected_tests():
    """Verify create_demo_selected_tests returns appropriate tests for each scenario."""
    from travelguard.demo import create_demo_selected_tests

    # UI drift should select booking drift test
    drift_tests = create_demo_selected_tests("booking-ui-drift")
    assert len(drift_tests) == 1
    assert drift_tests[0].test_id == "booking-drift"

    # API defect should select booking API test + booking E2E
    defect_tests = create_demo_selected_tests("booking-api-defect")
    assert len(defect_tests) == 2
    assert any(t.test_id == "booking-api" for t in defect_tests)
    assert any(t.test_id == "flight-booking" for t in defect_tests)

    # Environment failure should select booking API test
    env_tests = create_demo_selected_tests("environment-failure")
    assert len(env_tests) == 1
    assert env_tests[0].test_id == "booking-api"

    # Default fallback for unknown scenario
    default_tests = create_demo_selected_tests("unknown_scenario")
    assert default_tests is None


def test_create_demo_execution_results():
    """Verify create_demo_execution_results returns simulated failure results for each scenario."""
    from travelguard.demo import create_demo_execution_results

    drift_results = create_demo_execution_results("booking-ui-drift")
    assert len(drift_results) == 1
    assert drift_results[0].status == "failed"
    assert "Reserve Flight" in drift_results[0].failure.error_message or "Book Flight" in drift_results[0].failure.error_message

    defect_results = create_demo_execution_results("booking-api-defect")
    assert len(defect_results) == 1
    assert defect_results[0].status == "failed"
    assert "500" in defect_results[0].failure.error_message

    env_results = create_demo_execution_results("environment-failure")
    assert len(env_results) == 1
    assert env_results[0].status == "failed"
    assert "ECONNREFUSED" in env_results[0].failure.error_message

