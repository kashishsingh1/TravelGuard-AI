"""Coverage gap analyzer detecting when existing test inventory lacks coverage for new capabilities."""

import logging
from typing import List, Optional

from travelguard.models import (
    ChangeSet,
    CoverageAnalysis,
    CoverageStatus,
    ImpactAnalysisResult,
    SelectedTest,
)
from travelguard.test_inventory import TestInventoryRegistry, get_test_inventory

logger = logging.getLogger("travelguard.coverage")


class CoverageAnalyzer:
    """Analyzes whether selected tests adequately cover all changed capabilities."""

    def __init__(self, inventory: Optional[TestInventoryRegistry] = None):
        self.inventory = inventory or get_test_inventory()

    def analyze(
        self,
        changes: ChangeSet,
        impact: ImpactAnalysisResult,
        selected_tests: List[SelectedTest],
    ) -> CoverageAnalysis:
        """Evaluate coverage gaps against the changed code and capabilities."""
        diff_text = " ".join([f.diff for f in changes.files]).lower()
        changed_paths = changes.changed_paths

        missing_scenarios: List[str] = []

        # 1. Check for Promo Code / Discount additions
        has_promo_diff = any(
            kw in diff_text
            for kw in ("promo", "discount", "coupon", "voucher", "promocode")
        )
        has_promo_test = any("promo" in t.test_id or "coupon" in t.test_id for t in selected_tests)

        if has_promo_diff and not has_promo_test:
            missing_scenarios.append(
                "Applying promotional discount code during checkout and verifying discounted total fare"
            )

        # 2. Check for Seat Selection additions
        has_seat_diff = any(kw in diff_text for kw in ("seat", "seatmap", "seatselection"))
        has_seat_test = any("seat" in t.test_id for t in selected_tests)

        if has_seat_diff and not has_seat_test:
            missing_scenarios.append(
                "Selecting seat preferences and verifying seat allocation in booking confirmation"
            )

        # 3. Check for Travel Insurance additions
        has_insurance_diff = any(kw in diff_text for kw in ("insurance", "travelinsurance", "coverage"))
        has_insurance_test = any("insurance" in t.test_id for t in selected_tests)

        if has_insurance_diff and not has_insurance_test:
            missing_scenarios.append(
                "Opting into travel protection insurance and verifying premium addition to final price"
            )

        # 4. Check for New API Endpoints
        for file in changes.files:
            if "backend" in file.path or "api" in file.path:
                lines = [l for l in file.diff.splitlines() if l.startswith("+") and "@router." in l]
                for line in lines:
                    if "/promo" in line or "/discount" in line:
                        if not any("promo" in t.test_id for t in selected_tests):
                            missing_scenarios.append(
                                "Validating new promo code validation endpoint response and error handling"
                            )

        if missing_scenarios:
            return CoverageAnalysis(
                status=CoverageStatus.INSUFFICIENT,
                missing_scenarios=missing_scenarios,
                reason=(
                    f"Change introduces new capability '{missing_scenarios[0]}' "
                    f"that is not covered by any existing test in the test inventory."
                ),
            )

        return CoverageAnalysis(
            status=CoverageStatus.SUFFICIENT,
            missing_scenarios=[],
            reason="All modified paths and affected journeys are adequately covered by the selected test suite.",
        )
