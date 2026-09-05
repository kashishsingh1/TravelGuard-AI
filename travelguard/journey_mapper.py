"""Deterministic business journey mapping for code changes."""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from travelguard.models import BusinessJourney, ChangeSet, FileChange, JourneyCriticality
from travelguard.registry import JourneyRegistry, get_journey_registry


# Explicit deterministic path heuristics for SkyBook
DETERMINISTIC_RULES = [
    # Booking workflow
    {
        "patterns": ["booking", "passenger", "confirmation", "api/book"],
        "journey_id": "flight_booking",
        "capability": "Flight reservation and confirmation processing",
    },
    # Passenger details & validation
    {
        "patterns": ["passengerform", "errorbanner"],
        "journey_id": "passenger_details",
        "capability": "Traveler details capture and input validation",
    },
    # Flight results and selection
    {
        "patterns": ["flightresults", "selectflight", "select-flight"],
        "journey_id": "flight_selection",
        "capability": "Flight browsing, pricing display, and flight selection",
    },
    # Flight search
    {
        "patterns": ["searchform", "api/flights", "search.spec", "flights.py"],
        "journey_id": "flight_search",
        "capability": "Origin/destination flight discovery and schedule lookup",
    },
    # System health & diagnostics
    {
        "patterns": ["api/health", "api/llm", "llm/", "health.py", "test_llm"],
        "journey_id": "system_health",
        "capability": "Core infrastructure diagnostics and multi-provider LLM failover",
    },
]


class DeterministicMappingResult:
    """Result of deterministic journey mapping."""

    def __init__(
        self,
        journeys: List[BusinessJourney],
        candidate_tests: List[str],
        matched_components: List[str],
        capabilities: List[str],
    ):
        self.journeys = journeys
        self.candidate_tests = candidate_tests
        self.matched_components = matched_components
        self.capabilities = capabilities

    @property
    def has_matches(self) -> bool:
        return len(self.journeys) > 0

    @property
    def highest_criticality(self) -> JourneyCriticality:
        if not self.journeys:
            return JourneyCriticality.LOW
        order = [JourneyCriticality.LOW, JourneyCriticality.MEDIUM, JourneyCriticality.HIGH, JourneyCriticality.CRITICAL]
        highest = JourneyCriticality.LOW
        for j in self.journeys:
            if order.index(j.criticality) > order.index(highest):
                highest = j.criticality
        return highest


class JourneyMapper:
    """Maps changed files deterministically to business journeys and candidate tests."""

    def __init__(self, registry: Optional[JourneyRegistry] = None):
        self.registry = registry or get_journey_registry()

    def map_file(self, file_path: str) -> DeterministicMappingResult:
        """Map a single file path deterministically to affected journeys."""
        norm_path = file_path.replace("\\", "/").strip().lower()
        matched_journeys: Dict[str, BusinessJourney] = {}
        matched_components: Set[str] = set()
        matched_tests: Set[str] = set()
        matched_capabilities: Set[str] = set()

        # 1. Registry path lookup
        registry_matches = self.registry.find_journeys_by_path(norm_path)
        for j in registry_matches:
            matched_journeys[j.id] = j
            for c in j.components:
                if c.lower() in norm_path:
                    matched_components.add(c)
            for t in j.tests:
                matched_tests.add(t)

        # 2. Rule-based heuristic pattern matching
        for rule in DETERMINISTIC_RULES:
            if any(pattern in norm_path for pattern in rule["patterns"]):
                j = self.registry.get_journey(rule["journey_id"])
                if j:
                    matched_journeys[j.id] = j
                    for t in j.tests:
                        matched_tests.add(t)
                    matched_capabilities.add(rule["capability"])

        # Deduplicate and sort
        journeys_list = sorted(matched_journeys.values(), key=lambda j: j.workflow_stage)
        return DeterministicMappingResult(
            journeys=journeys_list,
            candidate_tests=sorted(matched_tests),
            matched_components=sorted(matched_components),
            capabilities=sorted(matched_capabilities),
        )

    def map_change_set(self, change_set: ChangeSet) -> DeterministicMappingResult:
        """Map all files in a change set to business journeys and aggregate candidate tests."""
        all_journeys: Dict[str, BusinessJourney] = {}
        all_components: Set[str] = set()
        all_tests: Set[str] = set()
        all_capabilities: Set[str] = set()

        for file_change in change_set.files:
            res = self.map_file(file_change.path)
            for j in res.journeys:
                all_journeys[j.id] = j
            all_components.update(res.matched_components)
            all_tests.update(res.candidate_tests)
            all_capabilities.update(res.capabilities)

        sorted_journeys = sorted(all_journeys.values(), key=lambda j: j.workflow_stage)
        return DeterministicMappingResult(
            journeys=sorted_journeys,
            candidate_tests=sorted(all_tests),
            matched_components=sorted(all_components),
            capabilities=sorted(all_capabilities),
        )
