"""Data models for TravelGuard change detection, business impact, intelligent test selection, test generation, and autonomous QA (Increment 4)."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChangeStatus(str, Enum):
    """Status of a file change."""
    MODIFIED = "modified"
    ADDED = "added"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNTRACKED = "untracked"


class ChangeSourceType(str, Enum):
    """Source of a change set."""
    WORKING_TREE = "working_tree"
    GIT_DIFF = "git_diff"
    FIXTURE = "fixture"
    CI_PR = "ci_pr"


class FileChange(BaseModel):
    """Represents a change to an individual file."""
    path: str = Field(..., description="File path relative to repository root")
    status: ChangeStatus = Field(default=ChangeStatus.MODIFIED, description="Status of the change")
    old_path: Optional[str] = Field(default=None, description="Previous file path if renamed")
    diff: str = Field(default="", description="Unified diff patch for this file")
    additions: int = Field(default=0, description="Number of lines added")
    deletions: int = Field(default=0, description="Number of lines deleted")


class ChangeSet(BaseModel):
    """Normalized representation of changes across the repository."""
    source: ChangeSourceType = Field(default=ChangeSourceType.WORKING_TREE, description="Source of the changes")
    base_ref: Optional[str] = Field(default=None, description="Base commit/branch reference if diffing refs")
    target_ref: Optional[str] = Field(default=None, description="Target commit/branch reference if diffing refs")
    files: List[FileChange] = Field(default_factory=list, description="List of file changes")
    summary: str = Field(default="", description="Summary of changed files")

    @property
    def changed_paths(self) -> List[str]:
        """List of changed file paths."""
        return [f.path for f in self.files]

    @property
    def total_additions(self) -> int:
        """Total lines added across all files."""
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        """Total lines deleted across all files."""
        return sum(f.deletions for f in self.files)


class JourneyCriticality(str, Enum):
    """Business criticality of a user journey."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BusinessJourney(BaseModel):
    """Definition of a machine-readable business user journey."""
    id: str = Field(..., description="Unique journey identifier")
    name: str = Field(..., description="Human-readable journey name")
    description: str = Field(..., description="Description of the customer journey")
    criticality: JourneyCriticality = Field(..., description="Business criticality")
    workflow_stage: int = Field(default=1, description="Sequential stage in the booking workflow")
    components: List[str] = Field(default_factory=list, description="Associated component names")
    frontend_paths: List[str] = Field(default_factory=list, description="Frontend file paths")
    api_paths: List[str] = Field(default_factory=list, description="Associated backend API routes or paths")
    tests: List[str] = Field(default_factory=list, description="Candidate tests covering this journey")


class JourneyImpact(BaseModel):
    """Impact of changes on a specific business journey."""
    journey_id: str = Field(..., description="Identifier of the affected journey")
    journey_name: str = Field(..., description="Name of the affected journey")
    impact_level: str = Field(..., description="Impact level: low, medium, high, critical")
    capability: str = Field(..., description="Specific business capability affected")


class RiskAssessment(BaseModel):
    """Calculated risk assessment for a change set."""
    level: str = Field(..., description="Risk classification: low, medium, high, critical")
    score: int = Field(..., description="Normalized risk score from 0 to 100")
    reason: str = Field(..., description="Human-readable explanation of the risk score")
    factors: Dict[str, Any] = Field(default_factory=dict, description="Factor breakdown contributing to score")


class ImpactAnalysisResult(BaseModel):
    """Complete structured impact analysis result."""
    summary: str = Field(..., description="Concise summary of what changed")
    change_type: str = Field(..., description="Classification: ui, api, business_logic, config, test, infra, cosmetic")
    is_behavioral: bool = Field(..., description="Whether change is functionally/behaviorally significant")
    affected_journeys: List[JourneyImpact] = Field(default_factory=list, description="Affected business workflows")
    risk: RiskAssessment = Field(..., description="Risk assessment")
    recommended_tests: List[str] = Field(default_factory=list, description="Recommended tests to run")
    business_impact: str = Field(..., description="Human-readable explanation of business risk")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="AI confidence score")
    provider_used: Optional[str] = Field(default=None, description="LLM provider name that performed analysis")
    fallback_used: bool = Field(default=False, description="Whether fallback LLM was engaged")


# ==============================================================================
# Increment 3: Intelligent Test Selection & AI Test Generation Models
# ==============================================================================

class TestPriority(str, Enum):
    """Test priority classification."""
    __test__ = False
    P0 = "P0"  # Critical business path (Booking, Confirmation, Core API)
    P1 = "P1"  # Important regression coverage (Search, Validation)
    P2 = "P2"  # Lower-risk / cosmetic coverage (Visual styling, display text)


class TestItem(BaseModel):
    """Machine-readable inventory item representing an existing test."""
    __test__ = False
    id: str = Field(..., description="Unique test identifier")
    name: str = Field(..., description="Human-readable test title")
    file: str = Field(..., description="File path relative to repository root")
    description: str = Field(..., description="What the test validates")
    business_journeys: List[str] = Field(default_factory=list, description="Journeys covered by this test")
    criticality: str = Field(default="high", description="critical | high | medium | low")
    priority_tier: TestPriority = Field(default=TestPriority.P1, description="Default priority tier")
    tags: List[str] = Field(default_factory=list, description="Test category tags")
    expected_duration_ms: int = Field(default=1000, description="Typical execution time in ms")


class SelectedTest(BaseModel):
    """Test selected for execution with priority and data-driven rationale."""
    test_id: str = Field(..., description="Test inventory ID")
    file: str = Field(..., description="Test file path")
    name: str = Field(..., description="Test title")
    priority: TestPriority = Field(..., description="P0 | P1 | P2")
    reason: str = Field(..., description="Data-driven reason for selecting this test")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0, description="Confidence in selection")


class SkippedTest(BaseModel):
    """Test deemed not necessary for the change, with reason."""
    test_id: str = Field(..., description="Test inventory ID")
    file: str = Field(..., description="Test file path")
    name: str = Field(..., description="Test title")
    reason: str = Field(..., description="Data-driven reason for skipping this test")


class CoverageStatus(str, Enum):
    """Coverage adequacy determination."""
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


class CoverageAnalysis(BaseModel):
    """Analysis of whether existing test inventory adequately covers the change."""
    status: CoverageStatus = Field(..., description="SUFFICIENT | INSUFFICIENT")
    missing_scenarios: List[str] = Field(default_factory=list, description="Missing test scenarios if any")
    reason: str = Field(..., description="Explanation of coverage status")


class GeneratedTest(BaseModel):
    """AI-generated Playwright test candidate."""
    file_path: str = Field(..., description="Target file path under tests/generated/")
    code: str = Field(..., description="Generated TypeScript Playwright test code")
    scenario_name: str = Field(..., description="Name of scenario covered")
    journey_id: str = Field(..., description="Target business journey")
    validation_status: str = Field(default="PENDING", description="PASSED | FAILED")
    validation_details: Optional[str] = Field(default=None, description="Static validator diagnostic output")


class TestIntelligenceResult(BaseModel):
    """Complete structured output of the Increment 3 pipeline."""
    __test__ = False
    impact: ImpactAnalysisResult = Field(..., description="Impact analysis result from Increment 2")
    selected_tests: List[SelectedTest] = Field(default_factory=list, description="Tests chosen for execution")
    skipped_tests: List[SkippedTest] = Field(default_factory=list, description="Tests intentionally omitted")
    coverage: CoverageAnalysis = Field(..., description="Coverage gap evaluation")
    generated_test: Optional[GeneratedTest] = Field(default=None, description="Candidate generated test if gap detected")


# ==============================================================================
# Increment 4: Autonomous Test Execution, Failure Diagnosis & Self-Healing
# ==============================================================================

class FailureClassification(str, Enum):
    """Classification of a test failure root cause."""
    PRODUCT_DEFECT = "PRODUCT_DEFECT"
    TEST_DRIFT = "TEST_DRIFT"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    UNKNOWN = "UNKNOWN"


class HealingStatus(str, Enum):
    """Outcome of a self-healing attempt."""
    HEALED_SUCCESSFULLY = "HEALED_SUCCESSFULLY"
    HEALING_FAILED = "HEALING_FAILED"
    PROPOSE_ONLY = "PROPOSE_ONLY"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    SKIPPED_PRODUCT_DEFECT = "SKIPPED_PRODUCT_DEFECT"
    SKIPPED_ENVIRONMENT_FAILURE = "SKIPPED_ENVIRONMENT_FAILURE"
    SKIPPED_UNKNOWN = "SKIPPED_UNKNOWN"
    SKIPPED_LOW_CONFIDENCE = "SKIPPED_LOW_CONFIDENCE"


class QualityStatus(str, Enum):
    """Final autonomous run quality verdict."""
    PASS = "PASS"
    PASS_WITH_HEALING = "PASS_WITH_HEALING"
    FAIL = "FAIL"
    REAL_DEFECT = "REAL_DEFECT"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    BLOCKED = "BLOCKED"


class TestFailureInfo(BaseModel):
    """Normalized, structured representation of a Playwright test failure."""
    __test__ = False
    test_id: str = Field(..., description="Test inventory ID")
    test_name: str = Field(..., description="Human-readable test name")
    test_file: str = Field(..., description="Test file path relative to repo root")
    status: str = Field(default="failed", description="Test status: passed | failed | timedOut | skipped")
    duration_ms: int = Field(default=0, description="Test execution duration in milliseconds")
    error_message: str = Field(default="", description="Primary error message")
    stack_trace: str = Field(default="", description="Stack trace if available")
    expected_value: Optional[str] = Field(default=None, description="Expected value in assertion")
    actual_value: Optional[str] = Field(default=None, description="Actual value in assertion")
    locator_used: Optional[str] = Field(default=None, description="Playwright locator that failed, if identifiable")
    screenshot_path: Optional[str] = Field(default=None, description="Path to failure screenshot")
    trace_path: Optional[str] = Field(default=None, description="Path to Playwright trace")
    test_source_snippet: Optional[str] = Field(default=None, description="Relevant source lines around failure")
    url: Optional[str] = Field(default=None, description="URL when failure occurred")
    browser: str = Field(default="chromium", description="Browser used")
    stdout: str = Field(default="", description="Captured stdout")
    stderr: str = Field(default="", description="Captured stderr")
    failure_line: Optional[int] = Field(default=None, description="Line number of failure in test file")


class RepairTarget(BaseModel):
    """Location and content of a proposed repair in a test file."""
    __test__ = False
    file: str = Field(..., description="Test file path")
    line: Optional[int] = Field(default=None, description="Line number of the broken locator/assertion")
    old_locator: str = Field(..., description="Current (broken) locator or assertion")
    new_locator: str = Field(..., description="Proposed replacement locator or assertion")


class DiagnosisResult(BaseModel):
    """Structured AI diagnosis of a test failure."""
    __test__ = False
    test_id: str = Field(..., description="Test inventory ID")
    test_file: str = Field(..., description="Test file path")
    classification: FailureClassification = Field(..., description="Root cause classification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence in classification")
    summary: str = Field(..., description="Human-readable diagnosis summary")
    evidence: List[str] = Field(default_factory=list, description="Evidence list supporting the classification")
    business_behavior_changed: bool = Field(default=False, description="Whether application business behavior actually changed")
    recommended_action: str = Field(default="INVESTIGATE", description="REPAIR_TEST | RAISE_BUG | INVESTIGATE | RETRY")
    repair_target: Optional[RepairTarget] = Field(default=None, description="Repair target if classification is TEST_DRIFT")
    provider_used: Optional[str] = Field(default=None, description="LLM provider used for diagnosis")


class RepairProposal(BaseModel):
    """Proposed minimal patch to a test file."""
    __test__ = False
    file: str = Field(..., description="Test file path")
    old_code: str = Field(..., description="Code to be replaced")
    new_code: str = Field(..., description="Replacement code")
    reason: str = Field(..., description="Human-readable justification for the patch")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the repair")


class ValidationResult(BaseModel):
    """Result of patch pre-application validation."""
    __test__ = False
    valid: bool = Field(..., description="Whether the patch passed all validation checks")
    checks_passed: List[str] = Field(default_factory=list, description="List of passed validation checks")
    checks_failed: List[str] = Field(default_factory=list, description="List of failed validation checks")
    reason: str = Field(default="", description="Human-readable validation outcome")


class HealingAttempt(BaseModel):
    """Record of a single healing attempt."""
    __test__ = False
    attempt_number: int = Field(..., description="Attempt index (1-based)")
    proposal: RepairProposal = Field(..., description="Patch proposal used in this attempt")
    validation: ValidationResult = Field(..., description="Pre-application validation result")
    applied: bool = Field(default=False, description="Whether the patch was physically applied")
    rerun_passed: bool = Field(default=False, description="Whether the repaired test passed on re-run")
    backup_path: Optional[str] = Field(default=None, description="Path to original test backup")


class HealingResult(BaseModel):
    """Complete self-healing lifecycle result for one test."""
    __test__ = False
    test_id: str = Field(..., description="Test inventory ID")
    test_file: str = Field(..., description="Test file path")
    status: HealingStatus = Field(..., description="Final healing outcome")
    failure_classification: FailureClassification = Field(..., description="Failure type that triggered healing")
    confidence: float = Field(default=0.0, description="Confidence of diagnosis")
    attempts: List[HealingAttempt] = Field(default_factory=list, description="History of healing attempts")
    original_locator: Optional[str] = Field(default=None, description="Original broken locator")
    replacement_locator: Optional[str] = Field(default=None, description="Replacement locator used")
    file_changed: Optional[str] = Field(default=None, description="File that was modified")
    healing_mode: str = Field(default="AUTO", description="AUTO | PROPOSE_ONLY")
    reason: str = Field(default="", description="Human-readable outcome explanation")


class TestExecutionResult(BaseModel):
    """Result of executing a single test file."""
    __test__ = False
    test_id: str = Field(..., description="Test inventory ID")
    test_file: str = Field(..., description="Test file path")
    test_name: str = Field(..., description="Test name")
    status: str = Field(..., description="passed | failed | timedOut | skipped")
    duration_ms: int = Field(default=0, description="Execution duration in milliseconds")
    failure: Optional[TestFailureInfo] = Field(default=None, description="Failure details if status is failed")
    stdout: str = Field(default="", description="Captured stdout")
    stderr: str = Field(default="", description="Captured stderr")
    screenshot_path: Optional[str] = Field(default=None, description="Screenshot path for failures")
    trace_path: Optional[str] = Field(default=None, description="Trace path for failures")


class QualityReport(BaseModel):
    """Final structured quality report for an autonomous QA run."""
    __test__ = False
    run_id: str = Field(..., description="Unique run identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    status: QualityStatus = Field(..., description="Overall run status")
    changed_files: int = Field(default=0, description="Number of changed files")
    selected_tests: int = Field(default=0, description="Number of tests selected")
    skipped_tests: int = Field(default=0, description="Number of tests skipped")
    passed: int = Field(default=0, description="Tests that passed")
    failed: int = Field(default=0, description="Tests that failed after all healing")
    healed: int = Field(default=0, description="Tests successfully healed")
    real_defects: int = Field(default=0, description="Tests classified as PRODUCT_DEFECT")
    environment_failures: int = Field(default=0, description="Tests classified as ENVIRONMENT_FAILURE")
    unknown_failures: int = Field(default=0, description="Tests with UNKNOWN classification")
    release_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Release confidence score")
    summary: str = Field(default="", description="Human-readable run summary")


class AutonomousRunResult(BaseModel):
    """Complete output of the Increment 4 autonomous QA pipeline."""
    __test__ = False
    run_id: str = Field(..., description="Unique run identifier")
    impact: ImpactAnalysisResult = Field(..., description="Impact analysis")
    selected_tests: List[SelectedTest] = Field(default_factory=list)
    skipped_tests: List[SkippedTest] = Field(default_factory=list)
    execution_results: List[TestExecutionResult] = Field(default_factory=list)
    diagnosis_results: List[DiagnosisResult] = Field(default_factory=list)
    healing_results: List[HealingResult] = Field(default_factory=list)
    quality_report: QualityReport = Field(..., description="Final quality verdict")
