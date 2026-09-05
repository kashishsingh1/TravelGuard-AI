"""AutonomousQAEngine — orchestrates the complete Increment 4 autonomous QA pipeline.

Full autonomous loop:
  1. detect_changes()
  2. analyze_impact()
  3. select_tests()
  4. execute_tests()
  5. collect_failures()
  6. diagnose_failures() [with Playwright MCP browser inspection]
  7. heal_if_safe()
  8. validate_repairs()
  9. rerun_repaired_tests()
  10. produce_quality_report()

Pipeline flow:
                  Git Change
                       ↓
                Change Detection
                       ↓
               Business Impact
                       ↓
                Test Selection
                       ↓
               Playwright Run
                       ↓
                   Failure?
                 /          \\
               NO            YES
               ↓              ↓
             PASS        Failure Diagnosis
                               ↓
                    ┌──────────┼──────────┐
                    ↓          ↓          ↓
                PRODUCT      DRIFT    ENVIRONMENT
                DEFECT         ↓         ↓
                  ↓          HEAL      REPORT
               REPORT          ↓
                             VALIDATE
                                 ↓
                               RERUN
                                 ↓
                           PASS / FAIL
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("travelguard.autonomous")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.llm.router import LLMService, get_llm_service

from travelguard.analyzer import ChangeImpactAnalyzer
from travelguard.change_detector import ChangeDetector, FixtureChangeSource, GitWorkingTreeSource
from travelguard.coverage_analyzer import CoverageAnalyzer
from travelguard.diagnosis_engine import FailureDiagnosisEngine
from travelguard.execution_engine import TestExecutionEngine
from travelguard.healing_engine import SelfHealingEngine
from travelguard.mcp_inspector import BrowserInspectionResult, PlaywrightMCPService
from travelguard.observability import record_run_metrics, trace_span
from travelguard.quality_gate import QualityGate, QualityGateDecision
from travelguard.release_confidence import ReleaseConfidenceEngine
from travelguard.models import (
    AutonomousRunResult,
    ChangeSet,
    DiagnosisResult,
    FailureClassification,
    HealingResult,
    HealingStatus,
    ImpactAnalysisResult,
    QualityReport,
    QualityStatus,
    SelectedTest,
    SkippedTest,
    TestExecutionResult,
    TestFailureInfo,
)
from travelguard.test_inventory import get_test_inventory
from travelguard.test_selector import LLMTestSelector


def _generate_run_id() -> str:
    """Generate a human-readable unique run ID."""
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return f"run-{ts}"


def _compute_release_confidence(
    selected: int,
    passed: int,
    healed: int,
    real_defects: int,
    env_failures: int,
    unknown_failures: int,
) -> float:
    """Compute a release confidence score (0.0–1.0)."""
    if selected == 0:
        return 1.0
    if real_defects > 0:
        return 0.0
    if env_failures > 0:
        return 0.3
    effective_passed = passed + healed
    base = effective_passed / selected if selected > 0 else 0.0
    # Penalise unknowns slightly
    penalty = unknown_failures * 0.05
    return max(0.0, min(1.0, base - penalty))


def _determine_quality_status(
    real_defects: int,
    env_failures: int,
    unknown_failures: int,
    healed: int,
    failed_after_healing: int,
) -> QualityStatus:
    """Determine the final quality verdict."""
    if real_defects > 0:
        return QualityStatus.REAL_DEFECT
    if env_failures > 0 or unknown_failures > 0:
        return QualityStatus.BLOCKED
    if failed_after_healing > 0:
        return QualityStatus.FAIL
    if healed > 0:
        return QualityStatus.PASS_WITH_HEALING
    return QualityStatus.PASS


class AutonomousQAEngine:
    """
    Orchestrates the complete autonomous QA pipeline from change detection to quality report.
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        app_base_url: str = "http://localhost:5173",
        artifacts_dir: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ):
        self.repo_root = repo_root or _REPO_ROOT
        self.artifacts_dir = artifacts_dir or (self.repo_root / "artifacts")
        self.app_base_url = app_base_url
        self._llm_service = llm_service

        # Lazy-init services
        self._impact_analyzer: Optional[ChangeImpactAnalyzer] = None
        self._test_selector: Optional[LLMTestSelector] = None
        self._execution_engine: Optional[TestExecutionEngine] = None
        self._diagnosis_engine: Optional[FailureDiagnosisEngine] = None
        self._healing_engine: Optional[SelfHealingEngine] = None
        self._mcp_service: Optional[PlaywrightMCPService] = None

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _llm(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    def _impact_analyzer_svc(self) -> ChangeImpactAnalyzer:
        if self._impact_analyzer is None:
            self._impact_analyzer = ChangeImpactAnalyzer(llm_service=self._llm())
        return self._impact_analyzer

    def _selector_svc(self) -> LLMTestSelector:
        if self._test_selector is None:
            inventory = get_test_inventory()
            self._test_selector = LLMTestSelector(llm_service=self._llm(), inventory=inventory)
        return self._test_selector

    def _executor_svc(self) -> TestExecutionEngine:
        if self._execution_engine is None:
            self._execution_engine = TestExecutionEngine(
                repo_root=self.repo_root,
                artifacts_dir=self.artifacts_dir,
            )
        return self._execution_engine

    def _diagnosis_svc(self) -> FailureDiagnosisEngine:
        if self._diagnosis_engine is None:
            self._diagnosis_engine = FailureDiagnosisEngine(llm_service=self._llm())
        return self._diagnosis_engine

    def _healing_svc(self) -> SelfHealingEngine:
        if self._healing_engine is None:
            self._healing_engine = SelfHealingEngine(
                repo_root=self.repo_root,
                artifacts_dir=self.artifacts_dir,
            )
        return self._healing_engine

    def _mcp_svc(self) -> PlaywrightMCPService:
        if self._mcp_service is None:
            self._mcp_service = PlaywrightMCPService(repo_root=self.repo_root)
        return self._mcp_service

    # ────────────────────────────────────────────────────────────────────────────
    # Main entry points
    # ────────────────────────────────────────────────────────────────────────────

    async def run(
        self,
        change_set: ChangeSet,
        mock_impact: Optional[dict] = None,
        demo_execution_results: Optional[List[TestExecutionResult]] = None,
        mock_selected_tests: Optional[List[SelectedTest]] = None,
    ) -> AutonomousRunResult:
        """
        Execute the full autonomous QA pipeline.

        Args:
            change_set: The change set to analyze
            mock_impact: Optional pre-built impact dict (for demo mode)
            demo_execution_results: Optional pre-built execution results (for demo mode)
            mock_selected_tests: Optional pre-built test selection (for fully deterministic demo mode;
                bypasses LLM test selector entirely)
        """
        run_id = _generate_run_id()
        ts = datetime.now(timezone.utc).isoformat()
        logger.info(f"[Autonomous] Starting run: {run_id}")

        # ── Step 1 & 2: Impact Analysis ──────────────────────────────────────
        logger.info("[Autonomous] Step 1/7: Impact analysis")
        impact: ImpactAnalysisResult = await self._impact_analyzer_svc().analyze(
            change_set=change_set,
            mock_response=mock_impact,
        )
        logger.info(f"[Autonomous] Impact: {impact.change_type} | Risk: {impact.risk.level}")

        # ── Step 3: Test Selection ─────────────────────────────────────────────
        logger.info("[Autonomous] Step 2/7: Test selection")
        if mock_selected_tests is not None:
            # Demo mode: use deterministic pre-built test selection (bypasses LLM)
            selected_tests = mock_selected_tests
            # Skipped = everything else in inventory
            inventory = get_test_inventory()
            selected_ids = {t.test_id for t in selected_tests}
            skipped_tests = [
                SkippedTest(
                    test_id=t.id,
                    file=t.file,
                    name=t.name,
                    reason="Not impacted by this demo scenario.",
                )
                for t in inventory.get_all()
                if t.id not in selected_ids
            ]
            logger.info(
                f"[Autonomous] Demo test selection: {len(selected_tests)} selected | "
                f"{len(skipped_tests)} skipped (deterministic)"
            )
        else:
            selected_tests, skipped_tests = await self._selector_svc().select(
                changes=change_set,
                impact=impact,
            )
        logger.info(f"[Autonomous] Selected: {len(selected_tests)} | Skipped: {len(skipped_tests)}")

        # ── Step 4: Test Execution ─────────────────────────────────────────────
        logger.info("[Autonomous] Step 3/7: Test execution")
        if demo_execution_results is not None:
            # Demo mode: use provided results (allows deterministic demos).
            # Any selected tests NOT covered by demo results are implicitly
            # passed (they are not the impacted tests; only failing ones are
            # injected into the demo). This ensures confidence arithmetic is
            # correct for the selected test count.
            demo_covered_ids = {r.test_id for r in demo_execution_results}
            implicit_passes: List[TestExecutionResult] = [
                TestExecutionResult(
                    test_id=t.test_id,
                    test_file=t.file,
                    test_name=t.name,
                    status="passed",
                    duration_ms=0,
                )
                for t in selected_tests
                if t.test_id not in demo_covered_ids
            ]
            execution_results = demo_execution_results + implicit_passes
            logger.info(
                f"[Autonomous] Using {len(demo_execution_results)} demo results + "
                f"{len(implicit_passes)} implicit passes for {len(selected_tests)} selected"
            )
        else:
            execution_results = await asyncio.to_thread(self._executor_svc().execute, selected_tests)

        passed_results = [r for r in execution_results if r.status == "passed"]
        failed_results = [r for r in execution_results if r.status != "passed"]
        logger.info(
            f"[Autonomous] Execution complete: {len(passed_results)} passed, {len(failed_results)} failed"
        )

        # ── Step 5–6: Failure Diagnosis ────────────────────────────────────────
        logger.info("[Autonomous] Step 4/7: Failure diagnosis")
        diagnosis_results: List[DiagnosisResult] = []

        for exec_result in failed_results:
            if exec_result.failure is None:
                continue

            # Browser inspection via Playwright MCP
            browser_state: Optional[BrowserInspectionResult] = None
            if demo_execution_results is None:
                # Only inspect browser in live mode
                try:
                    browser_state = self._mcp_svc().inspect_url(self.app_base_url)
                    logger.info(
                        f"[Autonomous] Browser inspection: "
                        f"{'available' if browser_state.available else 'unavailable'}"
                    )
                except Exception as mcp_err:
                    logger.warning(f"[Autonomous] MCP inspection failed: {mcp_err}")
                    browser_state = None

            diagnosis = await self._diagnosis_svc().diagnose(
                failure=exec_result.failure,
                change_set=change_set,
                browser_inspection=browser_state,
            )
            diagnosis_results.append(diagnosis)
            logger.info(
                f"[Autonomous] [{exec_result.test_id}] Diagnosis: "
                f"{diagnosis.classification.value} ({diagnosis.confidence:.0%})"
            )

        # ── Step 7: Self-Healing ───────────────────────────────────────────────
        logger.info("[Autonomous] Step 5/7: Self-healing")
        healing_results: List[HealingResult] = []
        healed_test_ids = set()

        for diagnosis in diagnosis_results:
            exec_result = next(
                (r for r in failed_results if r.test_id == diagnosis.test_id), None
            )
            if exec_result is None or exec_result.failure is None:
                continue

            # Browser state for healing proposals
            browser_state_for_healing = None
            if demo_execution_results is None:
                try:
                    browser_state_for_healing = self._mcp_svc().inspect_url(self.app_base_url)
                except Exception:
                    pass

            healing = await self._healing_svc().heal(
                failure=exec_result.failure,
                diagnosis=diagnosis,
                browser_inspection=browser_state_for_healing,
            )
            healing_results.append(healing)

            if healing.status == HealingStatus.HEALED_SUCCESSFULLY:
                healed_test_ids.add(diagnosis.test_id)
                logger.info(f"[Autonomous] HEALED: {diagnosis.test_id}")

        # ── Compute quality metrics ───────────────────────────────────────────
        logger.info("[Autonomous] Step 6/7: Computing quality report")

        n_selected = len(selected_tests)
        n_skipped = len(skipped_tests)
        n_passed = len(passed_results) + len(healed_test_ids)
        n_healed = len(healed_test_ids)

        # Count defect types from diagnosis
        n_real_defects = sum(
            1 for d in diagnosis_results
            if d.classification == FailureClassification.PRODUCT_DEFECT
        )
        n_env_failures = sum(
            1 for d in diagnosis_results
            if d.classification == FailureClassification.ENVIRONMENT_FAILURE
        )
        n_unknown = sum(
            1 for d in diagnosis_results
            if d.classification == FailureClassification.UNKNOWN
        )

        # Tests that still fail after healing
        n_still_failed = (
            len(failed_results)
            - len(healed_test_ids)
        )
        n_final_failed = max(0, n_still_failed)

        # Use ReleaseConfidenceEngine
        confidence_result = ReleaseConfidenceEngine.compute(
            selected_tests=selected_tests,
            passed_count=len(passed_results),
            healed_count=n_healed,
            diagnoses=diagnosis_results,
            risk_level=impact.risk.level,
        )

        quality_status = _determine_quality_status(
            real_defects=n_real_defects,
            env_failures=n_env_failures,
            unknown_failures=n_unknown,
            healed=n_healed,
            failed_after_healing=n_final_failed,
        )

        summary = self._build_summary(
            quality_status, n_selected, n_passed, n_healed, n_real_defects, n_env_failures
        )

        gate = QualityGate()
        gate_decision = gate.evaluate(
            QualityReport(
                run_id=run_id,
                timestamp=ts,
                status=quality_status,
                changed_files=len(change_set.files),
                selected_tests=n_selected,
                skipped_tests=n_skipped,
                passed=n_passed,
                failed=n_final_failed,
                healed=n_healed,
                real_defects=n_real_defects,
                environment_failures=n_env_failures,
                unknown_failures=n_unknown,
                release_confidence=confidence_result.confidence,
                summary=summary,
            ),
            confidence_result,
        )

        quality_report = QualityReport(
            run_id=run_id,
            timestamp=ts,
            status=quality_status,
            changed_files=len(change_set.files),
            selected_tests=n_selected,
            skipped_tests=n_skipped,
            passed=n_passed,
            failed=n_final_failed,
            healed=n_healed,
            real_defects=n_real_defects,
            environment_failures=n_env_failures,
            unknown_failures=n_unknown,
            release_confidence=confidence_result.confidence,
            release_decision=gate_decision.verdict,
            quality_gate_passed=gate_decision.passed_gate,
            confidence_explanation=confidence_result.breakdown.formula_explanation,
            summary=summary,
        )

        # Record Prometheus metrics
        record_run_metrics(
            status=quality_status.value,
            decision=gate_decision.action.value,
            confidence=confidence_result.confidence,
            healed=n_healed,
            defects=n_real_defects,
            env_failures=n_env_failures,
            failures_by_type={d.classification.value: 1 for d in diagnosis_results},
        )

        # ── Step 8: Save report ───────────────────────────────────────────────
        logger.info("[Autonomous] Step 7/7: Saving quality report")
        self._save_quality_report(run_id, quality_report, impact, gate_decision)

        logger.info(
            f"[Autonomous] Run complete: {quality_status.value} | "
            f"Confidence: {confidence_result.confidence:.0%} | Decision: {gate_decision.verdict} | Run ID: {run_id}"
        )

        return AutonomousRunResult(
            run_id=run_id,
            impact=impact,
            selected_tests=selected_tests,
            skipped_tests=skipped_tests,
            execution_results=execution_results,
            diagnosis_results=diagnosis_results,
            healing_results=healing_results,
            quality_report=quality_report,
            release_confidence_breakdown=confidence_result.breakdown.model_dump(),
            quality_gate_decision=gate_decision.model_dump(),
        )

    def _build_summary(
        self,
        status: QualityStatus,
        selected: int,
        passed: int,
        healed: int,
        real_defects: int,
        env_failures: int,
    ) -> str:
        """Build a human-readable run summary."""
        if status == QualityStatus.PASS:
            return f"All {selected} selected tests passed. No issues detected."
        if status == QualityStatus.PASS_WITH_HEALING:
            return f"{passed}/{selected} tests passed. {healed} test(s) self-healed successfully."
        if status == QualityStatus.REAL_DEFECT:
            return f"{real_defects} real product defect(s) detected. Test suite NOT automatically modified."
        if status == QualityStatus.BLOCKED:
            return f"Run blocked by environment failures ({env_failures}) or unknown issues."
        return "Test run completed with unresolved failures."

    def _save_quality_report(
        self,
        run_id: str,
        report: QualityReport,
        impact: Optional[ImpactAnalysisResult] = None,
        gate_decision: Optional[QualityGateDecision] = None,
    ) -> None:
        """Persist quality report to artifacts/runs/ and artifacts/quality/."""
        # 1. artifacts/runs/{run_id}.json
        runs_dir = self.artifacts_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        report_file = runs_dir / f"{run_id}.json"
        try:
            report_file.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"[Autonomous] Failed to save runs report: {exc}")

        # 2. artifacts/quality/quality-report.json
        quality_dir = self.artifacts_dir / "quality"
        quality_dir.mkdir(parents=True, exist_ok=True)
        quality_json = quality_dir / "quality-report.json"
        try:
            quality_json.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
            logger.info(f"[Autonomous] Quality JSON report saved: {quality_json}")
        except Exception as exc:
            logger.warning(f"[Autonomous] Failed to save quality-report.json: {exc}")

        # 3. artifacts/quality/quality-report.md
        quality_md = quality_dir / "quality-report.md"
        try:
            md_content = self._render_markdown_report(report, impact, gate_decision)
            quality_md.write_text(md_content, encoding="utf-8")
            logger.info(f"[Autonomous] Quality Markdown report saved: {quality_md}")
        except Exception as exc:
            logger.warning(f"[Autonomous] Failed to save quality-report.md: {exc}")

    def _render_markdown_report(
        self,
        report: QualityReport,
        impact: Optional[ImpactAnalysisResult] = None,
        gate_decision: Optional[QualityGateDecision] = None,
    ) -> str:
        """Render a clean GitHub-ready Markdown quality report."""
        verdict = gate_decision.verdict if gate_decision else report.status.value
        passed_gate = "PASSED" if (gate_decision and gate_decision.passed_gate) else ("BLOCKED" if report.real_defects > 0 else "UNKNOWN")

        lines = [
            "# TravelGuard AI — Autonomous QA & Release Quality Report",
            f"**Run ID:** `{report.run_id}`  ",
            f"**Timestamp:** `{report.timestamp}`  ",
            f"**Status:** `{report.status.value}`  ",
            f"**Release Decision:** **{verdict}** (`{passed_gate}`)  ",
            f"**Release Confidence:** **{int(report.release_confidence * 100)}%**  ",
            "",
            "---",
            "",
            "## Quality Gate Summary",
            f"- **Selected Tests:** {report.selected_tests}",
            f"- **Skipped Tests:** {report.skipped_tests}",
            f"- **Passed:** {report.passed}",
            f"- **Failed:** {report.failed}",
            f"- **Self-Healed:** {report.healed}",
            f"- **Real Product Defects:** {report.real_defects}",
            f"- **Environment Failures:** {report.environment_failures}",
            "",
            f"**Summary:** {report.summary}",
            "",
        ]

        if report.confidence_explanation:
            lines += [
                "### Release Confidence Rationale",
                f"> {report.confidence_explanation}",
                "",
            ]

        if impact:
            lines += [
                "## Impact Analysis",
                f"- **Change Type:** `{impact.change_type}`",
                f"- **Risk Level:** `{impact.risk.level.upper()}` ({impact.risk.score}/100)",
                f"- **Business Impact:** {impact.business_impact}",
                "",
            ]

        lines += [
            "---",
            "_Generated autonomously by TravelGuard AI — Quality Engineering for the AI Era._",
        ]
        return "\n".join(lines)
