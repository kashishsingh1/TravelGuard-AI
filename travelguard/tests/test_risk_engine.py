"""Unit tests for transparent risk scoring model."""

import pytest
from travelguard.models import ChangeSet, FileChange, JourneyCriticality
from travelguard.risk_engine import RiskEngine


def test_critical_journey_api_change_scores_critical():
    """Verify modifying a critical journey API results in CRITICAL risk (>=91)."""
    engine = RiskEngine()
    cs = ChangeSet(
        files=[
            FileChange(
                path="backend/app/api/booking.py",
                additions=15,
                deletions=5,
            )
        ]
    )

    assessment = engine.evaluate(
        change_set=cs,
        highest_criticality=JourneyCriticality.CRITICAL,
        change_type="api",
        is_behavioral=True,
    )

    assert assessment.level == "critical"
    assert assessment.score >= 91
    assert "journey_criticality" in assessment.factors
    assert "change_type" in assessment.factors


def test_booking_ui_behavioral_change_scores_high():
    """Verify modifying booking UI flow results in HIGH risk (71-90)."""
    engine = RiskEngine()
    cs = ChangeSet(
        files=[
            FileChange(
                path="frontend/src/components/PassengerForm.tsx",
                additions=10,
                deletions=2,
            )
        ]
    )

    assessment = engine.evaluate(
        change_set=cs,
        highest_criticality=JourneyCriticality.CRITICAL,
        change_type="ui",
        is_behavioral=True,
    )

    assert assessment.level in ("high", "critical")
    assert assessment.score >= 71


def test_cosmetic_ui_change_scores_low():
    """Verify purely cosmetic UI modifications receive LOW risk (<=30)."""
    engine = RiskEngine()
    cs = ChangeSet(
        files=[
            FileChange(
                path="frontend/src/components/SearchForm.tsx",
                additions=2,
                deletions=2,
            )
        ]
    )

    assessment = engine.evaluate(
        change_set=cs,
        highest_criticality=JourneyCriticality.MEDIUM,
        change_type="ui",
        is_behavioral=False,  # Cosmetic
    )

    assert assessment.level == "low"
    assert assessment.score <= 30


def test_test_only_changes_score_low():
    """Verify test-only modifications receive LOW risk."""
    engine = RiskEngine()
    cs = ChangeSet(
        files=[
            FileChange(
                path="tests/e2e/booking.spec.ts",
                additions=5,
                deletions=1,
            )
        ]
    )

    assessment = engine.evaluate(
        change_set=cs,
        highest_criticality=JourneyCriticality.CRITICAL,
        change_type="test",
        is_behavioral=False,
    )

    assert assessment.level == "low"
    assert assessment.score <= 30


def test_risk_explanation_present():
    """Verify risk assessment generates an explainable reason."""
    engine = RiskEngine()
    cs = ChangeSet(files=[FileChange(path="backend/app/api/flights.py")])
    assessment = engine.evaluate(
        change_set=cs,
        highest_criticality=JourneyCriticality.MEDIUM,
        change_type="api",
        is_behavioral=True,
    )
    assert assessment.reason != ""
    assert "MEDIUM" in assessment.reason or "API" in assessment.reason
