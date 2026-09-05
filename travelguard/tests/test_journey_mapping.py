"""Unit tests for deterministic journey mapping and registry loading."""

import pytest
from travelguard.journey_mapper import JourneyMapper
from travelguard.models import ChangeSet, FileChange, JourneyCriticality
from travelguard.registry import JourneyRegistry, get_journey_registry


def test_registry_loads_default_journeys():
    """Verify default journeys.yaml loads all 5 business journeys."""
    registry = get_journey_registry()
    journeys = registry.list_journeys()
    assert len(journeys) >= 5

    journey_ids = {j.id for j in journeys}
    assert "flight_search" in journey_ids
    assert "flight_selection" in journey_ids
    assert "passenger_details" in journey_ids
    assert "flight_booking" in journey_ids
    assert "system_health" in journey_ids


def test_map_booking_page_to_flight_booking():
    """Verify booking-related components map deterministically to flight_booking."""
    mapper = JourneyMapper()

    # Direct component match
    res1 = mapper.map_file("frontend/src/pages/BookingPage.tsx")
    assert res1.has_matches
    journey_ids = [j.id for j in res1.journeys]
    assert "flight_booking" in journey_ids

    # PassengerForm component match
    res2 = mapper.map_file("frontend/src/components/PassengerForm.tsx")
    assert res2.has_matches
    journey_ids2 = [j.id for j in res2.journeys]
    assert "flight_booking" in journey_ids2
    assert "passenger_details" in journey_ids2


def test_map_api_book_to_flight_booking():
    """Verify /api/book maps to flight_booking journey."""
    mapper = JourneyMapper()

    res = mapper.map_file("backend/app/api/booking.py")
    assert res.has_matches
    journey_ids = [j.id for j in res.journeys]
    assert "flight_booking" in journey_ids
    assert res.highest_criticality == JourneyCriticality.CRITICAL


def test_map_search_components_to_flight_search():
    """Verify search components map to flight_search journey."""
    mapper = JourneyMapper()

    res = mapper.map_file("frontend/src/components/SearchForm.tsx")
    assert res.has_matches
    journey_ids = [j.id for j in res.journeys]
    assert "flight_search" in journey_ids


def test_map_flight_results_to_flight_selection():
    """Verify FlightResults.tsx maps to flight_selection."""
    mapper = JourneyMapper()

    res = mapper.map_file("frontend/src/components/FlightResults.tsx")
    assert res.has_matches
    journey_ids = [j.id for j in res.journeys]
    assert "flight_selection" in journey_ids


def test_map_unknown_file():
    """Verify unknown file paths return clean empty matches without errors."""
    mapper = JourneyMapper()

    res = mapper.map_file("random/unrelated/script.py")
    assert not res.has_matches
    assert res.highest_criticality == JourneyCriticality.LOW
    assert len(res.candidate_tests) == 0


def test_map_change_set_aggregates_journeys():
    """Verify change set mapping combines multiple files and candidate tests."""
    mapper = JourneyMapper()
    cs = ChangeSet(
        files=[
            FileChange(path="frontend/src/components/SearchForm.tsx"),
            FileChange(path="backend/app/api/booking.py"),
        ]
    )
    res = mapper.map_change_set(cs)
    journey_ids = {j.id for j in res.journeys}
    assert "flight_search" in journey_ids
    assert "flight_booking" in journey_ids
    assert res.highest_criticality == JourneyCriticality.CRITICAL
    assert len(res.candidate_tests) >= 3
