"""Intelligent Test Selection Engine for TravelGuard AI."""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.llm.base import LLMResponse
from app.llm.router import LLMService, get_llm_service

from travelguard.models import (
    ChangeSet,
    ImpactAnalysisResult,
    JourneyCriticality,
    SelectedTest,
    SkippedTest,
    TestItem,
    TestPriority,
)
from travelguard.test_inventory import TestInventoryRegistry, get_test_inventory

logger = logging.getLogger("travelguard.selector")

TEST_SELECTION_SYSTEM_PROMPT = """You are TravelGuard AI, an expert Autonomous QA Engineer selecting tests for SkyBook travel application.
Your goal is to select ONLY the tests strictly necessary to validate the code change and prevent regressions, while skipping unrelated tests.

The priority tiers are:
- P0: Critical business path (Booking, Confirmation, Payment, Core API Contracts). Must run.
- P1: Important regression coverage (Search, Flight Selection, Form Validation).
- P2: Useful but lower-risk coverage (Cosmetic UI styling, minor display tweaks).

You will be given:
1. CHANGE: Changed files, diff patch, change type.
2. BUSINESS CONTEXT: Affected journeys and criticality.
3. TEST INVENTORY: List of all available tests in the repository.

You MUST return a valid JSON object following this exact schema:
{
  "selected_tests": [
    {
      "test_id": "<must match an ID from the test inventory>",
      "priority": "<P0 | P1 | P2>",
      "reason": "<specific, data-driven explanation of why this test validates the change>",
      "confidence": <float between 0.0 and 1.0>
    }
  ],
  "skipped_tests": [
    {
      "test_id": "<must match an ID from the test inventory>",
      "reason": "<specific reason why this test is safe to skip for this change>"
    }
  ]
}

DO NOT include any text outside the JSON. Return only the JSON object.
"""


def extract_json(raw_text: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM output safely."""
    text = raw_text.strip()
    if not text:
        raise ValueError("LLM returned empty response")

    # Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Code fence
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Outermost brackets
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = re.sub(r",\s*([\]}])", r"\1", text[start : end + 1])
        return json.loads(cleaned)

    raise ValueError(f"Could not extract valid JSON from LLM output: {text[:200]}")


class DeterministicTestSelector:
    """Fast deterministic test selector using inventory metadata and journey mappings."""

    def __init__(self, inventory: Optional[TestInventoryRegistry] = None):
        self.inventory = inventory or get_test_inventory()

    def select(
        self,
        changes: ChangeSet,
        impact: ImpactAnalysisResult,
    ) -> Tuple[List[SelectedTest], List[SkippedTest]]:
        """Deterministically select tests based on affected journeys and changed paths."""
        all_tests = self.inventory.get_all()
        selected: List[SelectedTest] = []
        skipped: List[SkippedTest] = []

        affected_journey_ids = {j.journey_id for j in impact.affected_journeys}
        changed_paths = changes.changed_paths
        diff_lower = " ".join([f.diff.lower() for f in changes.files])

        for test in all_tests:
            # Check overlap between test journeys and affected journeys
            shared_journeys = set(test.business_journeys).intersection(affected_journey_ids)

            # Check specific path associations
            is_api_change = any("api" in p or "backend" in p for p in changed_paths)
            is_validation_change = "validation" in diff_lower or "validate" in diff_lower or "error" in diff_lower

            should_select = False
            priority = test.priority_tier
            reason = ""

            if test.id == "booking-api" and is_api_change:
                should_select = True
                priority = TestPriority.P0
                reason = "Backend API route or data contracts were modified; exercises core booking API endpoints."
            elif test.id == "flight-booking" and "flight_booking" in affected_journey_ids:
                should_select = True
                priority = TestPriority.P0
                reason = "Modifications affect the critical Flight Booking journey; validates end-to-end user checkout and ticket issuance."
            elif test.id == "passenger-validation" and ("flight_booking" in affected_journey_ids or is_validation_change):
                should_select = True
                priority = TestPriority.P0 if is_validation_change else TestPriority.P1
                reason = "Passenger information inputs or submission rules altered; validates field rejection and error messaging."
            elif test.id == "flight-selection" and "flight_selection" in affected_journey_ids:
                should_select = True
                priority = TestPriority.P1
                reason = "Flight selection or pricing calculation modified; validates flight card selection flow."
            elif test.id == "flight-search" and "flight_search" in affected_journey_ids:
                should_select = True
                priority = TestPriority.P2 if impact.change_type == "cosmetic" else TestPriority.P1
                reason = f"Flight Search form modified ({impact.change_type}); validates query submission and result rendering."
            elif shared_journeys:
                should_select = True
                reason = f"Exercises journey '{list(shared_journeys)[0]}' impacted by changed files."

            if should_select:
                selected.append(
                    SelectedTest(
                        test_id=test.id,
                        file=test.file,
                        name=test.name,
                        priority=priority,
                        reason=reason,
                        confidence=0.95,
                    )
                )
            else:
                skip_reason = f"Change in '{', '.join(changed_paths[:2])}' does not impact '{test.name}'."
                skipped.append(
                    SkippedTest(
                        test_id=test.id,
                        file=test.file,
                        name=test.name,
                        reason=skip_reason,
                    )
                )

        return selected, skipped


class LLMTestSelector:
    """Intelligent test selector leveraging multi-tier LLM reasoning."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        inventory: Optional[TestInventoryRegistry] = None,
    ):
        self.llm_service = llm_service or get_llm_service()
        self.inventory = inventory or get_test_inventory()
        self.deterministic_fallback = DeterministicTestSelector(self.inventory)

    async def select(
        self,
        changes: ChangeSet,
        impact: ImpactAnalysisResult,
    ) -> Tuple[List[SelectedTest], List[SkippedTest]]:
        """Reason about change impact and select optimal test subset via LLM."""
        all_tests = self.inventory.get_all()
        inventory_payload = [
            {
                "id": t.id,
                "name": t.name,
                "file": t.file,
                "description": t.description,
                "business_journeys": t.business_journeys,
                "criticality": t.criticality,
                "default_priority": t.priority_tier.value,
            }
            for t in all_tests
        ]

        prompt_user = {
            "change_summary": impact.summary,
            "change_type": impact.change_type,
            "is_behavioral": impact.is_behavioral,
            "risk_level": impact.risk.level,
            "risk_score": impact.risk.score,
            "affected_journeys": [
                {
                    "journey_id": j.journey_id,
                    "journey_name": j.journey_name,
                    "capability": j.capability,
                    "impact_level": j.impact_level,
                }
                for j in impact.affected_journeys
            ],
            "changed_files": [
                {
                    "path": f.path,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "diff_snippet": f.diff[:1200],
                }
                for f in changes.files
            ],
            "available_test_inventory": inventory_payload,
        }

        try:
            response: LLMResponse = await self.llm_service.generate(
                prompt=f"Analyze this change and select relevant tests:\n\n{json.dumps(prompt_user, indent=2)}",
                system_prompt=TEST_SELECTION_SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.2,
            )

            data = extract_json(response.content)
            raw_selected = data.get("selected_tests", [])
            raw_skipped = data.get("skipped_tests", [])

            # Map into typed models
            test_map = {t.id: t for t in all_tests}
            selected_ids = set()
            selected_tests: List[SelectedTest] = []
            skipped_tests: List[SkippedTest] = []

            for item in raw_selected:
                t_id = item.get("test_id")
                if t_id in test_map:
                    test = test_map[t_id]
                    selected_ids.add(t_id)
                    p_val = item.get("priority", test.priority_tier.value).upper()
                    priority = TestPriority.P0 if p_val == "P0" else (TestPriority.P2 if p_val == "P2" else TestPriority.P1)
                    selected_tests.append(
                        SelectedTest(
                            test_id=test.id,
                            file=test.file,
                            name=test.name,
                            priority=priority,
                            reason=item.get("reason", f"Selected to validate {test.name}"),
                            confidence=float(item.get("confidence", 0.9)),
                        )
                    )

            # Collect skipped tests
            for item in raw_skipped:
                t_id = item.get("test_id")
                if t_id in test_map and t_id not in selected_ids:
                    test = test_map[t_id]
                    skipped_tests.append(
                        SkippedTest(
                            test_id=test.id,
                            file=test.file,
                            name=test.name,
                            reason=item.get("reason", "Not impacted by this change"),
                        )
                    )

            # Ensure any tests omitted by LLM are accounted for in skipped
            for test in all_tests:
                if test.id not in selected_ids and not any(s.test_id == test.id for s in skipped_tests):
                    skipped_tests.append(
                        SkippedTest(
                            test_id=test.id,
                            file=test.file,
                            name=test.name,
                            reason=f"No direct or indirect dependencies on '{impact.summary}'.",
                        )
                    )

            if selected_tests:
                return selected_tests, skipped_tests

            logger.warning("[LLMSelector] LLM returned 0 selected tests; engaging deterministic fallback.")
            return self.deterministic_fallback.select(changes, impact)

        except Exception as exc:
            logger.warning(f"[LLMSelector] LLM selection failed ({exc}); engaging deterministic fallback.")
            return self.deterministic_fallback.select(changes, impact)
