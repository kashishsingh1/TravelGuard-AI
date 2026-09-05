"""Orchestrator for the complete Increment 3 Autonomous Test Intelligence Pipeline."""

import logging
from typing import Optional

from app.llm.router import LLMService, get_llm_service

from travelguard.analyzer import ChangeImpactAnalyzer
from travelguard.coverage_analyzer import CoverageAnalyzer
from travelguard.models import ChangeSet, GeneratedTest, TestIntelligenceResult
from travelguard.test_generator import AITestGenerator
from travelguard.test_inventory import TestInventoryRegistry, get_test_inventory
from travelguard.test_selector import LLMTestSelector

logger = logging.getLogger("travelguard.pipeline")


class TestIntelligencePipeline:
    """
    Executes the complete end-to-end Test Intelligence flow:
    Git Change -> Change Detection -> Impact & Risk -> Test Inventory ->
    Intelligent Test Selection (P0/P1/P2) -> Coverage Gap Detection ->
    AI Test Generation -> Static Validation (STOP).
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        inventory: Optional[TestInventoryRegistry] = None,
    ):
        self.llm_service = llm_service or get_llm_service()
        self.inventory = inventory or get_test_inventory()
        self.impact_analyzer = ChangeImpactAnalyzer(llm_service=self.llm_service)
        self.test_selector = LLMTestSelector(llm_service=self.llm_service, inventory=self.inventory)
        self.coverage_analyzer = CoverageAnalyzer(inventory=self.inventory)
        self.test_generator = AITestGenerator(llm_service=self.llm_service)

    async def run(
        self,
        change_set: ChangeSet,
        mock_response: Optional[dict] = None,
    ) -> TestIntelligenceResult:
        """Run the end-to-end intelligence pipeline on a change set."""
        logger.info(f"[Pipeline] Starting intelligence analysis for {len(change_set.files)} files")

        # 1. Business Impact & Risk Analysis
        impact = await self.impact_analyzer.analyze(
            change_set=change_set,
            mock_response=mock_response,
        )

        # 2. Intelligent Test Selection (Deterministic + LLM)
        selected_tests, skipped_tests = await self.test_selector.select(
            changes=change_set,
            impact=impact,
        )

        # 3. Coverage Gap Detection
        coverage = self.coverage_analyzer.analyze(
            changes=change_set,
            impact=impact,
            selected_tests=selected_tests,
        )

        # 4. AI Test Generation & Static Validation (Triggered ONLY if coverage is insufficient)
        generated_test: Optional[GeneratedTest] = None
        if coverage.status.value == "INSUFFICIENT" and coverage.missing_scenarios:
            missing_scenario = coverage.missing_scenarios[0]
            logger.info(f"[Pipeline] Coverage gap identified: '{missing_scenario}'. Generating candidate test.")
            generated_test = await self.test_generator.generate_test(
                changes=change_set,
                impact=impact,
                missing_scenario=missing_scenario,
            )

        return TestIntelligenceResult(
            impact=impact,
            selected_tests=selected_tests,
            skipped_tests=skipped_tests,
            coverage=coverage,
            generated_test=generated_test,
        )
