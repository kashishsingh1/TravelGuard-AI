"""Data models for TravelGuard change detection and business impact analysis."""

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
