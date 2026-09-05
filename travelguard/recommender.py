"""Test recommendation engine mapping affected journeys to SkyBook automated test suites."""

from typing import List, Set
from travelguard.models import BusinessJourney, JourneyImpact


class TestRecommender:
    """Recommends specific tests to execute based on affected journeys and change classification."""

    def recommend(
        self,
        journeys: List[BusinessJourney],
        change_type: str,
        is_behavioral: bool,
        ai_recommended: List[str],
    ) -> List[str]:
        """Aggregate, prioritize, and deduplicate test recommendations."""
        recommended_set: Set[str] = set()

        # 1. Add all deterministic tests from affected journeys
        for journey in journeys:
            for test in journey.tests:
                recommended_set.add(test)

        # 2. Incorporate AI-suggested tests if valid
        for test in ai_recommended:
            clean_test = test.strip()
            if clean_test:
                recommended_set.add(clean_test)

        # 3. Sort and prioritize: E2E and API tests for critical changes
        tests_list = list(recommended_set)

        if change_type == "api":
            # Sort API tests first
            tests_list.sort(key=lambda t: 0 if "api" in t.lower() or "test_api" in t.lower() else 1)
        elif change_type == "ui":
            # Sort E2E tests first
            tests_list.sort(key=lambda t: 0 if "e2e" in t.lower() or ".spec." in t.lower() else 1)
        else:
            tests_list.sort()

        # If not behavioral (cosmetic), limit to light UI / search tests if present
        if not is_behavioral and len(tests_list) > 2:
            tests_list = [t for t in tests_list if "e2e" in t.lower()][:2] or tests_list[:2]

        return tests_list
