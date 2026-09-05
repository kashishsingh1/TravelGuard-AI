"""Transparent risk scoring model for code changes."""

from typing import Any, Dict, List, Optional
from travelguard.models import ChangeSet, JourneyCriticality, RiskAssessment


class RiskEngine:
    """Calculates risk level and transparent scoring based on deterministic rules and AI classification."""

    CRITICALITY_BASE = {
        JourneyCriticality.CRITICAL: 50,
        JourneyCriticality.HIGH: 35,
        JourneyCriticality.MEDIUM: 20,
        JourneyCriticality.LOW: 10,
    }

    CHANGE_TYPE_WEIGHTS = {
        "api": 30,
        "business_logic": 25,
        "config": 25,
        "ui": 20,
        "cosmetic": 5,
        "infra": 15,
        "test": 5,
        "docs": 0,
    }

    def evaluate(
        self,
        change_set: ChangeSet,
        highest_criticality: JourneyCriticality,
        change_type: str,
        is_behavioral: bool,
        ai_risk_hint: Optional[str] = None,
        ai_reason: Optional[str] = None,
    ) -> RiskAssessment:
        """Calculate transparent risk score (0-100) and assign risk level."""
        factors: Dict[str, Any] = {}

        # 1. Base score from journey criticality
        base_score = self.CRITICALITY_BASE.get(highest_criticality, 10)
        factors["journey_criticality"] = {
            "level": highest_criticality.value,
            "points": base_score,
        }

        # 2. Change type points
        c_type = change_type.lower()
        if not is_behavioral and c_type == "ui":
            c_type = "cosmetic"
        type_points = self.CHANGE_TYPE_WEIGHTS.get(c_type, 15)
        factors["change_type"] = {
            "type": c_type,
            "points": type_points,
        }

        # 3. Behavioral modifier
        behavioral_points = 15 if is_behavioral else -10
        factors["behavioral_impact"] = {
            "is_behavioral": is_behavioral,
            "points": behavioral_points,
        }

        # 4. Diff volume points
        volume_points = 0
        total_lines = change_set.total_additions + change_set.total_deletions
        if total_lines > 200:
            volume_points = 10
        elif total_lines > 50:
            volume_points = 5
        factors["diff_volume"] = {
            "lines_changed": total_lines,
            "points": volume_points,
        }

        # Sum and clamp to [5, 100]
        raw_score = base_score + type_points + behavioral_points + volume_points
        # If test-only or docs-only change, cap at 25
        if c_type in ("test", "docs"):
            raw_score = min(raw_score, 25)

        # If cosmetic UI, cap at 30
        if not is_behavioral and c_type == "cosmetic":
            raw_score = min(raw_score, 25)

        # If critical journey and API change, guarantee high/critical
        if highest_criticality == JourneyCriticality.CRITICAL and c_type in ("api", "business_logic") and is_behavioral:
            raw_score = max(raw_score, 92)
        elif highest_criticality in (JourneyCriticality.CRITICAL, JourneyCriticality.HIGH) and is_behavioral:
            raw_score = max(raw_score, 75)

        final_score = max(5, min(100, raw_score))

        # Determine level
        if final_score >= 91:
            level = "critical"
        elif final_score >= 71:
            level = "high"
        elif final_score >= 31:
            level = "medium"
        else:
            level = "low"

        # Build transparent explanation
        if ai_reason:
            reason = ai_reason
        else:
            reason = (
                f"Change affects {highest_criticality.value.upper()} criticality journey "
                f"with {change_type.upper()} modification "
                f"({'behavioral' if is_behavioral else 'cosmetic'})."
            )

        return RiskAssessment(
            level=level,
            score=final_score,
            reason=reason,
            factors=factors,
        )
