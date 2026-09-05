"""SelfHealingEngine — controlled, evidence-based self-repair of stale Playwright tests.

Safety principles:
  - ONLY activates for TEST_DRIFT classification
  - Requires confidence >= threshold (default 0.90) for AUTO mode
  - Below threshold → PROPOSE_ONLY (never auto-applies)
  - Creates a backup before any modification
  - Applies MINIMAL patches only (single locator replacement)
  - Validates the patch before applying
  - Re-runs the repaired test to confirm
  - Max 2 healing attempts then stops — no infinite loops
  - Never heals PRODUCT_DEFECT, ENVIRONMENT_FAILURE, or UNKNOWN

Configuration via environment variables:
  TRAVELGUARD_HEALING_MODE       AUTO | PROPOSE_ONLY  (default: AUTO)
  TRAVELGUARD_HEALING_CONFIDENCE 0.0–1.0              (default: 0.90)
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("travelguard.healing")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _REPO_ROOT / "tests"
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from travelguard.models import (
    DiagnosisResult,
    FailureClassification,
    HealingAttempt,
    HealingResult,
    HealingStatus,
    RepairProposal,
    TestFailureInfo,
    ValidationResult,
)


MAX_HEALING_ATTEMPTS = 2
DEFAULT_CONFIDENCE_THRESHOLD = 0.90
DEFAULT_HEALING_MODE = "AUTO"


def _get_healing_mode() -> str:
    return os.environ.get("TRAVELGUARD_HEALING_MODE", DEFAULT_HEALING_MODE).upper()


def _get_confidence_threshold() -> float:
    try:
        return float(os.environ.get("TRAVELGUARD_HEALING_CONFIDENCE", DEFAULT_CONFIDENCE_THRESHOLD))
    except ValueError:
        return DEFAULT_CONFIDENCE_THRESHOLD


class SelfHealingEngine:
    """
    Controlled, evidence-based self-healing engine for stale Playwright tests.

    Healing lifecycle:
      Failure → Diagnosis (TEST_DRIFT) → Identify patch → Validate → Apply → Re-run → Report
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        tests_dir: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None,
        healing_mode: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        max_attempts: int = MAX_HEALING_ATTEMPTS,
    ):
        self.repo_root = repo_root or _REPO_ROOT
        self.tests_dir = tests_dir or _TESTS_DIR
        self.artifacts_dir = artifacts_dir or (self.repo_root / "artifacts")
        self.healing_mode = (healing_mode or _get_healing_mode()).upper()
        self.confidence_threshold = confidence_threshold or _get_confidence_threshold()
        self.max_attempts = max_attempts
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        (self.artifacts_dir / "healing").mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────

    async def heal(
        self,
        failure: TestFailureInfo,
        diagnosis: DiagnosisResult,
        browser_inspection=None,
    ) -> HealingResult:
        """
        Attempt to self-heal the test identified in the diagnosis.
        Returns HealingResult with full lifecycle record.
        """
        logger.info(f"[Healing] Evaluating healing for: {diagnosis.test_id}")

        # ── Guard: only heal TEST_DRIFT ───────────────────────────────────────
        if diagnosis.classification != FailureClassification.TEST_DRIFT:
            status_map = {
                FailureClassification.PRODUCT_DEFECT: HealingStatus.SKIPPED_PRODUCT_DEFECT,
                FailureClassification.ENVIRONMENT_FAILURE: HealingStatus.SKIPPED_ENVIRONMENT_FAILURE,
                FailureClassification.UNKNOWN: HealingStatus.SKIPPED_UNKNOWN,
            }
            skip_status = status_map.get(diagnosis.classification, HealingStatus.NOT_ATTEMPTED)
            reason = (
                f"Healing skipped: classification is {diagnosis.classification.value}. "
                f"Only TEST_DRIFT cases are automatically repaired."
            )
            logger.info(f"[Healing] {reason}")
            return HealingResult(
                test_id=diagnosis.test_id,
                test_file=diagnosis.test_file,
                status=skip_status,
                failure_classification=diagnosis.classification,
                confidence=diagnosis.confidence,
                reason=reason,
                healing_mode=self.healing_mode,
            )

        # ── Guard: confidence threshold ───────────────────────────────────────
        if diagnosis.confidence < self.confidence_threshold:
            reason = (
                f"Healing skipped: confidence {diagnosis.confidence:.0%} is below "
                f"threshold {self.confidence_threshold:.0%}. Using PROPOSE_ONLY mode."
            )
            logger.info(f"[Healing] {reason}")
            # Still generate a proposal even though we won't apply it
            proposal = self._build_proposal(failure, diagnosis, browser_inspection)
            return HealingResult(
                test_id=diagnosis.test_id,
                test_file=diagnosis.test_file,
                status=HealingStatus.SKIPPED_LOW_CONFIDENCE,
                failure_classification=diagnosis.classification,
                confidence=diagnosis.confidence,
                original_locator=proposal.old_code if proposal else None,
                replacement_locator=proposal.new_code if proposal else None,
                reason=reason,
                healing_mode="PROPOSE_ONLY",
            )

        # ── Propose-only mode ─────────────────────────────────────────────────
        if self.healing_mode == "PROPOSE_ONLY":
            proposal = self._build_proposal(failure, diagnosis, browser_inspection)
            reason = "PROPOSE_ONLY mode — patch generated but NOT applied automatically."
            logger.info(f"[Healing] {reason}")
            return HealingResult(
                test_id=diagnosis.test_id,
                test_file=diagnosis.test_file,
                status=HealingStatus.PROPOSE_ONLY,
                failure_classification=diagnosis.classification,
                confidence=diagnosis.confidence,
                original_locator=proposal.old_code if proposal else None,
                replacement_locator=proposal.new_code if proposal else None,
                reason=reason,
                healing_mode=self.healing_mode,
            )

        # ── AUTO mode: attempt healing up to max_attempts ─────────────────────
        attempts: List[HealingAttempt] = []
        backup_path: Optional[str] = None

        for attempt_num in range(1, self.max_attempts + 1):
            logger.info(f"[Healing] Attempt {attempt_num}/{self.max_attempts}")

            # Build repair proposal
            proposal = self._build_proposal(failure, diagnosis, browser_inspection)
            if not proposal:
                logger.warning("[Healing] Could not build a repair proposal. Stopping.")
                break

            # Validate the patch
            validation = self._validate_patch(proposal)
            logger.info(f"[Healing] Validation: {'PASS' if validation.valid else 'FAIL'} — {validation.reason}")

            attempt = HealingAttempt(
                attempt_number=attempt_num,
                proposal=proposal,
                validation=validation,
                applied=False,
                rerun_passed=False,
                backup_path=backup_path,
            )

            if not validation.valid:
                attempts.append(attempt)
                logger.warning(f"[Healing] Patch validation failed: {validation.checks_failed}")
                continue

            # Create backup before first modification
            if backup_path is None:
                backup_path = self._backup_test(proposal.file, diagnosis.test_id)
                attempt.backup_path = backup_path

            # Apply the patch
            applied = self._apply_patch(proposal)
            attempt.applied = applied

            if not applied:
                logger.warning("[Healing] Patch application failed.")
                attempts.append(attempt)
                continue

            # Log the healing event
            self._log_healing_event(diagnosis, proposal, attempt_num)

            # Re-run the repaired test
            rerun_passed = self._rerun_test(failure.test_file, diagnosis.test_id, failure.test_name)
            attempt.rerun_passed = rerun_passed
            attempts.append(attempt)

            if rerun_passed:
                logger.info(f"[Healing] Test healed successfully on attempt {attempt_num}!")
                return HealingResult(
                    test_id=diagnosis.test_id,
                    test_file=diagnosis.test_file,
                    status=HealingStatus.HEALED_SUCCESSFULLY,
                    failure_classification=diagnosis.classification,
                    confidence=diagnosis.confidence,
                    attempts=attempts,
                    original_locator=proposal.old_code,
                    replacement_locator=proposal.new_code,
                    file_changed=proposal.file,
                    healing_mode=self.healing_mode,
                    reason=f"Test healed successfully on attempt {attempt_num}. Re-run passed.",
                )
            else:
                logger.warning(f"[Healing] Re-run failed on attempt {attempt_num}. Restoring backup.")
                if backup_path:
                    self._restore_backup(backup_path, proposal.file)

        # All attempts exhausted
        logger.warning(f"[Healing] All {self.max_attempts} healing attempts failed.")
        return HealingResult(
            test_id=diagnosis.test_id,
            test_file=diagnosis.test_file,
            status=HealingStatus.HEALING_FAILED,
            failure_classification=diagnosis.classification,
            confidence=diagnosis.confidence,
            attempts=attempts,
            healing_mode=self.healing_mode,
            reason=f"Healing failed after {self.max_attempts} attempts. Test restored from backup.",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Proposal generation
    # ─────────────────────────────────────────────────────────────────────────

    def _build_proposal(
        self,
        failure: TestFailureInfo,
        diagnosis: DiagnosisResult,
        browser_inspection=None,
    ) -> Optional[RepairProposal]:
        """Build a minimal repair proposal from diagnosis evidence."""
        # Use repair_target from diagnosis if available
        if diagnosis.repair_target and diagnosis.repair_target.old_locator and diagnosis.repair_target.new_locator:
            rt = diagnosis.repair_target
            old_code = rt.old_locator
            new_code = rt.new_locator
            reason = diagnosis.summary
            return RepairProposal(
                file=rt.file or failure.test_file,
                old_code=old_code,
                new_code=new_code,
                reason=reason,
                confidence=diagnosis.confidence,
            )

        # Fallback: use locator from failure info + browser inspection
        if failure.locator_used and browser_inspection and browser_inspection.available:
            old_name = self._extract_name_from_locator(failure.locator_used)
            if old_name:
                candidates = browser_inspection.find_similar_to(old_name)
                if candidates:
                    replacement = candidates[0]
                    new_locator = replacement.to_playwright_locator()
                    return RepairProposal(
                        file=failure.test_file,
                        old_code=failure.locator_used,
                        new_code=new_locator,
                        reason=f"Browser inspection found '{replacement.name or replacement.text}' as candidate replacement.",
                        confidence=diagnosis.confidence * 0.9,
                    )

        # Cannot build a proposal
        logger.warning("[Healing] Cannot build proposal — insufficient repair information")
        return None

    def _extract_name_from_locator(self, locator: str) -> Optional[str]:
        """Extract human-readable name from a Playwright locator."""
        m = re.search(r"name:\s*['\"]([^'\"]+)['\"]", locator)
        if m:
            return m.group(1)
        m2 = re.search(r"getByText\(['\"]([^'\"]+)['\"]\)", locator)
        if m2:
            return m2.group(1)
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_patch(self, proposal: RepairProposal) -> ValidationResult:
        """
        Validate a repair proposal before applying it.

        Checks:
          1. Test file exists
          2. Old code exists in the file (exact match)
          3. Proposed patch is non-empty
          4. Old code != new code (actual change)
          5. New code looks like a valid Playwright locator
        """
        passed = []
        failed = []

        # 1. File exists
        test_file_abs = self._resolve_abs(proposal.file)
        if test_file_abs and test_file_abs.exists():
            passed.append("file_exists")
        else:
            failed.append(f"file_not_found: {proposal.file}")
            return ValidationResult(valid=False, checks_passed=passed, checks_failed=failed,
                                    reason="Test file does not exist.")

        # Read file content
        try:
            content = test_file_abs.read_text(encoding="utf-8")
        except Exception as e:
            failed.append(f"file_read_error: {e}")
            return ValidationResult(valid=False, checks_passed=passed, checks_failed=failed,
                                    reason=f"Cannot read test file: {e}")

        # 2. Old code exists in file
        if proposal.old_code in content:
            passed.append("old_code_found")
        else:
            failed.append(f"old_code_not_found: {proposal.old_code[:100]!r}")
            return ValidationResult(valid=False, checks_passed=passed, checks_failed=failed,
                                    reason="The old code to replace was not found in the test file.")

        # 3. New code is non-empty
        if proposal.new_code and proposal.new_code.strip():
            passed.append("new_code_nonempty")
        else:
            failed.append("new_code_empty")
            return ValidationResult(valid=False, checks_passed=passed, checks_failed=failed,
                                    reason="Proposed replacement code is empty.")

        # 4. Old != New
        if proposal.old_code != proposal.new_code:
            passed.append("codes_differ")
        else:
            failed.append("old_equals_new")
            return ValidationResult(valid=False, checks_passed=passed, checks_failed=failed,
                                    reason="Old code and new code are identical — no change would occur.")

        # 5. New code looks like a valid Playwright selector/locator
        valid_locator_patterns = [
            r"getByRole\(",
            r"getByLabel\(",
            r"getByText\(",
            r"getByPlaceholder\(",
            r"locator\(",
            r"\[data-testid=",
        ]
        is_valid_locator = any(re.search(p, proposal.new_code) for p in valid_locator_patterns)
        if is_valid_locator:
            passed.append("valid_playwright_locator")
        else:
            # Allow it but warn
            passed.append("locator_format_uncertain")
            logger.warning(f"[Healing] New code may not be a standard Playwright locator: {proposal.new_code!r}")

        return ValidationResult(
            valid=True,
            checks_passed=passed,
            checks_failed=failed,
            reason=f"All {len(passed)} validation checks passed.",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Backup, apply, restore
    # ─────────────────────────────────────────────────────────────────────────

    def _backup_test(self, test_file: str, test_id: str) -> str:
        """Create a timestamped backup of the test file before modification."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.artifacts_dir / "healing" / f"{ts}_{test_id}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        src = self._resolve_abs(test_file)
        if src and src.exists():
            dest = backup_dir / src.name
            shutil.copy2(str(src), str(dest))
            logger.info(f"[Healing] Backup created: {dest}")
            return str(dest)
        return ""

    def _apply_patch(self, proposal: RepairProposal) -> bool:
        """Apply the minimal patch to the test file."""
        test_file_abs = self._resolve_abs(proposal.file)
        if not test_file_abs or not test_file_abs.exists():
            logger.error(f"[Healing] Cannot apply patch — file not found: {proposal.file}")
            return False

        try:
            content = test_file_abs.read_text(encoding="utf-8")
            if proposal.old_code not in content:
                logger.error("[Healing] old_code not found in file — validation should have caught this")
                return False

            # Minimal replacement — only first occurrence
            new_content = content.replace(proposal.old_code, proposal.new_code, 1)
            test_file_abs.write_text(new_content, encoding="utf-8")
            logger.info(f"[Healing] Patch applied to: {test_file_abs}")
            return True
        except Exception as exc:
            logger.error(f"[Healing] Patch application error: {exc}")
            return False

    def _restore_backup(self, backup_path: str, test_file: str) -> None:
        """Restore the original test file from backup."""
        try:
            src = Path(backup_path)
            dest = self._resolve_abs(test_file)
            if src.exists() and dest:
                shutil.copy2(str(src), str(dest))
                logger.info(f"[Healing] Backup restored: {dest}")
        except Exception as exc:
            logger.error(f"[Healing] Backup restoration failed: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # Re-run
    # ─────────────────────────────────────────────────────────────────────────

    def _rerun_test(self, test_file: str, test_id: str, test_name: str) -> bool:
        """Re-run a single repaired test and return True if it passes."""
        logger.info(f"[Healing] Re-running repaired test: {test_file}")
        rel_file = Path(test_file)
        if rel_file.parts and rel_file.parts[0] == "tests":
            rel_for_playwright = str(Path(*rel_file.parts[1:]))
        else:
            rel_for_playwright = str(rel_file)

        try:
            result = subprocess.run(
                ["npx", "playwright", "test", rel_for_playwright, "--reporter", "list"],
                cwd=str(self.tests_dir),
                capture_output=True,
                text=True,
                timeout=120,
                env=dict(os.environ),
            )
            passed = result.returncode == 0
            icon = "PASS" if passed else "FAIL"
            logger.info(f"[Healing] Re-run result: {icon}")
            return passed
        except subprocess.TimeoutExpired:
            logger.error("[Healing] Re-run timed out")
            return False
        except FileNotFoundError:
            logger.error("[Healing] playwright not found for re-run")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Logging and utilities
    # ─────────────────────────────────────────────────────────────────────────

    def _log_healing_event(
        self, diagnosis: DiagnosisResult, proposal: RepairProposal, attempt: int
    ) -> None:
        """Write a structured healing event log to artifacts/healing/."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        event = {
            "event": "healing_attempt",
            "timestamp": ts,
            "test": diagnosis.test_id,
            "test_file": diagnosis.test_file,
            "classification": diagnosis.classification.value,
            "confidence": diagnosis.confidence,
            "attempt": attempt,
            "old_code": proposal.old_code,
            "new_code": proposal.new_code,
            "reason": proposal.reason,
        }
        log_file = self.artifacts_dir / "healing" / f"event_{ts}_{diagnosis.test_id}.json"
        try:
            log_file.write_text(json.dumps(event, indent=2), encoding="utf-8")
        except Exception:
            pass
        logger.info(f"[Healing] Event logged: {log_file}")

    def _resolve_abs(self, file_path: str) -> Optional[Path]:
        """Resolve file path to absolute Path."""
        p = Path(file_path)
        if p.is_absolute():
            return p
        candidate = self.repo_root / file_path
        if candidate.exists():
            return candidate
        return self.repo_root / file_path
