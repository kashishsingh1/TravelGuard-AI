"""FailureDiagnosisEngine — classifies test failures using evidence-based AI reasoning.

Classification categories:
  PRODUCT_DEFECT     — The application behavior is broken
  TEST_DRIFT         — The test automation is stale (locator drift, label change)
  ENVIRONMENT_FAILURE — Infrastructure/environment issue (backend unreachable, browser crash)
  UNKNOWN            — Insufficient evidence to classify

The engine uses:
  1. Deterministic fast-path for obvious environment failures (no LLM call)
  2. LLM analysis with structured evidence for ambiguous cases
  3. Browser inspection state from PlaywrightMCPService as additional evidence
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("travelguard.diagnosis")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.llm.router import LLMService, get_llm_service

from travelguard.security import scrub_secrets
from travelguard.models import (
    ChangeSet,
    DiagnosisResult,
    FailureClassification,
    RepairTarget,
    TestFailureInfo,
)

DIAGNOSIS_SYSTEM_PROMPT = """You are TravelGuard AI, an expert autonomous QA engineer diagnosing a software test failure.

Your task is to determine the ROOT CAUSE of the test failure using the supplied evidence.

IMPORTANT RULES:
- Do NOT assume the test is wrong just because it failed.
- Do NOT assume the application is broken just because the test failed.
- Use the SUPPLIED EVIDENCE to reason carefully.
- Consider all three failure categories equally before concluding.

FAILURE CATEGORIES:
1. PRODUCT_DEFECT: The application behavior is broken. The test is validating the correct expected behavior, but the application no longer delivers it. Example: API returns 500, booking fails, data is wrong.

2. TEST_DRIFT: The test automation is stale. The application's business behavior is unchanged, but a UI locator, button label, or assertion value has changed. The test needs to be updated, NOT the application. Example: button text changed from "Book Flight" to "Reserve Flight" while booking still works.

3. ENVIRONMENT_FAILURE: Infrastructure or environment is unavailable. Example: backend server not running, browser crash, network error.

4. UNKNOWN: Insufficient evidence to classify with confidence.

You MUST respond with a valid JSON object ONLY. No text before or after.

JSON schema:
{
  "classification": "PRODUCT_DEFECT | TEST_DRIFT | ENVIRONMENT_FAILURE | UNKNOWN",
  "confidence": <float 0.0-1.0>,
  "summary": "<1-2 sentence explanation of what failed and why>",
  "evidence": ["<evidence item 1>", "<evidence item 2>", ...],
  "business_behavior_changed": <true if the application business function itself changed, false if only test automation is stale>,
  "recommended_action": "REPAIR_TEST | RAISE_BUG | INVESTIGATE | RETRY",
  "repair_target": {
    "file": "<test file path>",
    "line": <line number or null>,
    "old_locator": "<broken locator expression>",
    "new_locator": "<proposed replacement locator>"
  }
}

Only include "repair_target" when classification is TEST_DRIFT and you have strong evidence for a specific repair.
"""


# Patterns that indicate environment failure without needing an LLM call
_ENVIRONMENT_FAILURE_PATTERNS = [
    r"net::ERR_CONNECTION_REFUSED",
    r"connect ECONNREFUSED",
    r"ECONNREFUSED",
    r"ERR_CONNECTION_TIMED_OUT",
    r"net::ERR_NAME_NOT_RESOLVED",
    r"Target (?:page|context|browser) (?:has been )?closed",
    r"Browser.*closed",
    r"playwright/npx not found",
    r"ENVIRONMENT_FAILURE",
    r"Cannot connect to backend",
    r"Failed to fetch",
    r"ENOTFOUND",
    r"socket hang up",
]

# Patterns that strongly suggest TEST_DRIFT without needing full LLM analysis
_TEST_DRIFT_SIGNALS = [
    r"locator\.nth\(0\).*not visible",
    r"Expected.*to be visible",
    r"Timeout.*waiting for",
    r"No element.*matching",
    r"getByRole.*not found",
    r"locator.*resolved to.*hidden",
]


def _is_environment_failure(error_message: str, stderr: str) -> bool:
    """Deterministically detect environment failures — avoids unnecessary LLM calls."""
    combined = (error_message + " " + stderr).lower()
    if "waiting for" in combined or "timed out waiting for" in combined or "getbyrole" in combined or "getbytestid" in combined:
        return False
    for pattern in _ENVIRONMENT_FAILURE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return True
    return False


def _build_evidence_prompt(
    failure: TestFailureInfo,
    change_set: ChangeSet,
    browser_context: str = "",
) -> str:
    """Construct a structured evidence prompt for the LLM diagnosis."""

    # Diff snippets (truncated per file to avoid context blowup)
    diff_info = []
    for fc in change_set.files:
        diff_snippet = fc.diff[:1500] if fc.diff else "(no diff available)"
        if len(fc.diff) > 1500:
            diff_snippet += "\n... [diff truncated]"
        diff_info.append(
            f"File: {fc.path} ({fc.status.value}, +{fc.additions}/-{fc.deletions})\n"
            f"```diff\n{diff_snippet}\n```"
        )

    changed_files_text = "\n\n".join(diff_info) if diff_info else "No changed files detected."

    # Build structured evidence block
    evidence = f"""=== TEST FAILURE REPORT ===
Test ID:       {failure.test_id}
Test File:     {failure.test_file}
Test Name:     {failure.test_name}
Status:        {failure.status}
Duration:      {failure.duration_ms}ms
Browser:       {failure.browser}

=== ERROR ===
{failure.error_message[:1500]}

=== STACK TRACE ===
{failure.stack_trace[:1000] if failure.stack_trace else "(none)"}

=== LOCATOR USED ===
{failure.locator_used or "(not identified)"}

=== EXPECTED vs ACTUAL ===
Expected: {failure.expected_value or "(not parsed)"}
Actual:   {failure.actual_value or "(not parsed)"}

=== TEST SOURCE SNIPPET ===
{failure.test_source_snippet or "(not available)"}

=== CHANGED APPLICATION FILES ===
{changed_files_text}

=== BROWSER INSPECTION (Live Application State) ===
{browser_context or "(browser inspection not available)"}
"""
    return scrub_secrets(evidence)


def _extract_json_from_llm(raw_text: str) -> dict:
    """Extract JSON from LLM output, handling markdown fences and partial output."""
    text = raw_text.strip()
    if not text:
        raise ValueError("Empty LLM response")

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Code fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        # Remove trailing commas
        cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:300]}")


class FailureDiagnosisEngine:
    """
    Classifies test failures into PRODUCT_DEFECT / TEST_DRIFT / ENVIRONMENT_FAILURE / UNKNOWN.

    Uses a two-stage approach:
    1. Deterministic fast-path for clear environment failures (no LLM cost)
    2. LLM analysis with structured evidence for nuanced classification
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm_service = llm_service

    def _get_llm_service(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    async def diagnose(
        self,
        failure: TestFailureInfo,
        change_set: ChangeSet,
        browser_inspection=None,  # Optional[BrowserInspectionResult]
    ) -> DiagnosisResult:
        """
        Diagnose a test failure and return a structured DiagnosisResult.

        Args:
            failure: Normalized failure info from TestExecutionEngine
            change_set: The change set that triggered the test run
            browser_inspection: Optional live browser state from PlaywrightMCPService
        """
        logger.info(f"[Diagnosis] Diagnosing failure for: {failure.test_id}")

        # ── Stage 1: Deterministic environment failure detection ──────────────
        if _is_environment_failure(failure.error_message, failure.stderr):
            logger.info(f"[Diagnosis] Deterministic classification: ENVIRONMENT_FAILURE")
            return DiagnosisResult(
                test_id=failure.test_id,
                test_file=failure.test_file,
                classification=FailureClassification.ENVIRONMENT_FAILURE,
                confidence=0.97,
                summary=(
                    f"Test '{failure.test_name}' failed due to an infrastructure or "
                    f"environment issue. The application server or browser is unreachable."
                ),
                evidence=[
                    f"Error indicates network/environment failure: {failure.error_message[:200]}",
                    "Deterministic classification — no LLM call required.",
                ],
                business_behavior_changed=False,
                recommended_action="RETRY",
                repair_target=None,
                provider_used="deterministic",
            )

        # ── Stage 2: LLM-based diagnosis with evidence ────────────────────────
        browser_context = ""
        if browser_inspection is not None:
            browser_context = browser_inspection.to_context_string()

        evidence_prompt = _build_evidence_prompt(failure, change_set, browser_context)

        provider_used = "unknown"
        try:
            llm = self._get_llm_service()
            response = await llm.generate(
                prompt=evidence_prompt,
                system_prompt=DIAGNOSIS_SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.1,
            )
            provider_used = response.provider
            parsed = _extract_json_from_llm(response.content)
        except Exception as exc:
            logger.warning(f"[Diagnosis] LLM failed ({exc}); using heuristic fallback")
            parsed = self._heuristic_fallback(failure, change_set)
            provider_used = "heuristic"

        # ── Parse and validate LLM output ────────────────────────────────────
        raw_class = parsed.get("classification", "UNKNOWN")
        try:
            classification = FailureClassification(raw_class)
        except ValueError:
            classification = FailureClassification.UNKNOWN

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        summary = parsed.get("summary", "Diagnosis could not be determined.")
        evidence = parsed.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        business_behavior_changed = bool(parsed.get("business_behavior_changed", False))
        recommended_action = parsed.get("recommended_action", "INVESTIGATE")

        # Parse repair target
        repair_target = None
        raw_repair = parsed.get("repair_target")
        if raw_repair and classification == FailureClassification.TEST_DRIFT:
            try:
                repair_target = RepairTarget(
                    file=raw_repair.get("file", failure.test_file),
                    line=raw_repair.get("line"),
                    old_locator=raw_repair.get("old_locator", ""),
                    new_locator=raw_repair.get("new_locator", ""),
                )
            except Exception:
                repair_target = None

        # If MCP found a replacement element and LLM agrees it's TEST_DRIFT, augment repair
        if (
            browser_inspection is not None
            and browser_inspection.available
            and classification == FailureClassification.TEST_DRIFT
            and failure.locator_used
            and repair_target is None
        ):
            # Try to auto-identify repair target from browser inspection
            old_name = self._extract_name_from_locator(failure.locator_used)
            if old_name:
                candidate = browser_inspection.find_replacement_for_locator_direct(
                    failure.locator_used, old_name
                ) if hasattr(browser_inspection, "find_replacement_for_locator_direct") else None
                if candidate is None:
                    similar = browser_inspection.find_similar_to(old_name)
                    candidate = similar[0] if similar else None
                if candidate:
                    repair_target = RepairTarget(
                        file=failure.test_file,
                        line=failure.failure_line,
                        old_locator=failure.locator_used,
                        new_locator=candidate.to_playwright_locator(),
                    )
                    evidence.append(
                        f"Browser inspection found candidate: {candidate.to_playwright_locator()}"
                    )

        logger.info(f"[Diagnosis] Result: {classification.value} (confidence={confidence:.2f})")

        return DiagnosisResult(
            test_id=failure.test_id,
            test_file=failure.test_file,
            classification=classification,
            confidence=confidence,
            summary=summary,
            evidence=evidence,
            business_behavior_changed=business_behavior_changed,
            recommended_action=recommended_action,
            repair_target=repair_target,
            provider_used=provider_used,
        )

    def _extract_name_from_locator(self, locator: str) -> Optional[str]:
        """Extract the human-readable name from a Playwright locator string."""
        # getByRole('button', { name: 'Book Flight' })
        m = re.search(r"name:\s*['\"]([^'\"]+)['\"]", locator)
        if m:
            return m.group(1)
        # getByText('Book Flight')
        m2 = re.search(r"getByText\(['\"]([^'\"]+)['\"]\)", locator)
        if m2:
            return m2.group(1)
        return None

    def _heuristic_fallback(self, failure: TestFailureInfo, change_set: ChangeSet) -> dict:
        """Deterministic heuristic when LLM is unavailable."""
        error = failure.error_message.lower()
        stderr = failure.stderr.lower()
        combined = error + " " + stderr

        # Strong API/backend failure signals → PRODUCT_DEFECT
        if any(kw in combined for kw in ["500", "internal server error", "422", "400 bad request"]):
            return {
                "classification": "PRODUCT_DEFECT",
                "confidence": 0.75,
                "summary": "Test failure indicates a backend API error (HTTP 4xx/5xx).",
                "evidence": ["Error message contains HTTP error status code."],
                "business_behavior_changed": True,
                "recommended_action": "RAISE_BUG",
            }

        # Locator / visibility failure → possibly TEST_DRIFT
        changed_ui_files = [
            f.path for f in change_set.files
            if any(f.path.endswith(ext) for ext in (".tsx", ".jsx", ".html", ".css"))
        ]
        if changed_ui_files and ("locator" in combined or "visible" in combined or "timeout" in combined):
            return {
                "classification": "TEST_DRIFT",
                "confidence": 0.70,
                "summary": "UI file changed and test locator/visibility assertion failed. Likely TEST_DRIFT.",
                "evidence": [
                    f"Changed UI files: {', '.join(changed_ui_files)}",
                    "Locator or visibility error detected in failure message.",
                ],
                "business_behavior_changed": False,
                "recommended_action": "REPAIR_TEST",
            }

        return {
            "classification": "UNKNOWN",
            "confidence": 0.40,
            "summary": "Could not classify failure without LLM. Manual investigation required.",
            "evidence": ["LLM unavailable; heuristic analysis inconclusive."],
            "business_behavior_changed": False,
            "recommended_action": "INVESTIGATE",
        }
