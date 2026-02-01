"""Tests for activity Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.activity import (
    LocalOperator,
    ActivityRecommendation,
    ActivityRecommendations,
    OperatorKnowledgeEntry,
)


class TestLocalOperator:
    """Tests for LocalOperator schema."""

    def test_valid_operator(self):
        """Basic operator with required fields."""
        op = LocalOperator(
            name="Test Operator",
            destination="Tarifa",
            activities=["kitesurfing"],
            specialty="Kite lessons",
        )
        assert op.name == "Test Operator"
        assert len(op.activities) == 1

    def test_operator_with_all_fields(self):
        """Operator with all fields."""
        op = LocalOperator(
            name="Test Operator",
            destination="Tarifa",
            activities=["kitesurfing", "surfing"],
            specialty="Water sports",
            price_range="$80-150/lesson",
            contact="test@example.com",
            notes="Great instructor",
        )
        assert op.price_range == "$80-150/lesson"
        assert op.contact == "test@example.com"


class TestActivityRecommendation:
    """Tests for ActivityRecommendation schema."""

    def test_valid_recommendation(self):
        """Basic recommendation."""
        rec = ActivityRecommendation(
            activity="Kitesurfing",
            destination="Tarifa",
            why_now="Peak wind season",
            skill_level="Intermediate",
            duration="2 hours",
            cost_estimate="$100",
        )
        assert rec.activity == "Kitesurfing"

    def test_recommendation_with_operator(self):
        """Recommendation with operator."""
        op = LocalOperator(
            name="Test School",
            destination="Tarifa",
            activities=["kitesurfing"],
            specialty="Lessons",
        )
        rec = ActivityRecommendation(
            activity="Kitesurfing",
            destination="Tarifa",
            why_now="Great conditions",
            skill_level="Beginner",
            duration="3 hours",
            cost_estimate="$150",
            operator=op,
            tips=["Book morning sessions", "Bring sunscreen"],
        )
        assert rec.operator.name == "Test School"
        assert len(rec.tips) == 2


class TestActivityRecommendations:
    """Tests for ActivityRecommendations schema."""

    def _make_rec(self, activity: str) -> ActivityRecommendation:
        return ActivityRecommendation(
            activity=activity,
            destination="Tarifa",
            why_now="Good conditions",
            skill_level="All levels",
            duration="2 hours",
            cost_estimate="$80",
        )

    def test_valid_recommendations(self):
        """Valid recommendations."""
        recs = ActivityRecommendations(
            destination="Tarifa",
            recommendations=[self._make_rec("Kitesurfing")],
            summary="Great options",
        )
        assert len(recs.recommendations) == 1

    def test_max_recommendations(self):
        """Can have up to 5 recommendations."""
        recs = ActivityRecommendations(
            destination="Tarifa",
            recommendations=[self._make_rec(f"Activity {i}") for i in range(5)],
            summary="Many options",
        )
        assert len(recs.recommendations) == 5

    def test_rejects_empty(self):
        """Rejects empty recommendations."""
        with pytest.raises(ValidationError):
            ActivityRecommendations(
                destination="Tarifa",
                recommendations=[],
                summary="None",
            )


class TestOperatorKnowledgeEntry:
    """Tests for OperatorKnowledgeEntry schema."""

    def test_valid_entry(self):
        """Valid knowledge entry."""
        entry = OperatorKnowledgeEntry(
            name="Test School",
            destination="Tarifa",
            activities=["kitesurfing", "surfing"],
            specialty="Water sports lessons",
            price_range="$80-150",
        )
        assert entry.name == "Test School"
        assert len(entry.activities) == 2
