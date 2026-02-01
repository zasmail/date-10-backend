"""Tests for destination knowledge base Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.knowledge.schemas import (
    ActivitySeasonality,
    ClimateData,
    Destination,
    DestinationKnowledgeBase,
)


class TestActivitySeasonality:
    """Tests for ActivitySeasonality validation."""

    def test_valid_months(self):
        """Verify months in range 1-12 are accepted."""
        activity = ActivitySeasonality(
            season=[1, 6, 12],
            conditions="Good conditions",
        )
        assert activity.season == [1, 6, 12]

    def test_rejects_month_zero(self):
        """Month 0 should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            ActivitySeasonality(
                season=[0, 6, 12],
                conditions="Good conditions",
            )
        assert "Month must be between 1 and 12" in str(exc_info.value)

    def test_rejects_month_thirteen(self):
        """Month 13 should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            ActivitySeasonality(
                season=[1, 13],
                conditions="Good conditions",
            )
        assert "Month must be between 1 and 12" in str(exc_info.value)

    def test_optional_fields(self):
        """Optional fields should work correctly."""
        activity = ActivitySeasonality(
            season=[5, 6, 7],
            conditions="Wind conditions",
            reliability="80%",
            skill_level="intermediate",
            notes="Extra notes",
        )
        assert activity.reliability == "80%"
        assert activity.skill_level == "intermediate"
        assert activity.notes == "Extra notes"


class TestClimateData:
    """Tests for ClimateData validation."""

    def test_valid_months(self):
        """Verify valid month ranges are accepted."""
        climate = ClimateData(
            best_months=[4, 5, 9, 10],
            avg_temp_c={"summer": 28, "winter": 14},
            rainy_months=[11, 12, 1, 2],
        )
        assert climate.best_months == [4, 5, 9, 10]
        assert climate.rainy_months == [11, 12, 1, 2]

    def test_rejects_invalid_best_months(self):
        """Invalid best_months should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            ClimateData(
                best_months=[0, 4, 5],
                avg_temp_c={"summer": 28},
            )
        assert "Month must be between 1 and 12" in str(exc_info.value)

    def test_rejects_invalid_rainy_months(self):
        """Invalid rainy_months should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            ClimateData(
                best_months=[4, 5],
                avg_temp_c={"summer": 28},
                rainy_months=[13],
            )
        assert "Month must be between 1 and 12" in str(exc_info.value)


class TestDestination:
    """Tests for Destination model validation."""

    def test_has_required_fields(self, knowledge_base: DestinationKnowledgeBase):
        """All destinations must have required fields."""
        for dest in knowledge_base.destinations:
            assert dest.name, "name is required"
            assert dest.country, "country is required"
            assert dest.activities, "activities is required"
            assert dest.climate, "climate is required"
            assert dest.logistics, "logistics is required"
            assert dest.accommodation, "accommodation is required"
            assert dest.vibe, "vibe is required"
            assert dest.why_go, "why_go is required"
            assert dest.why_skip, "why_skip is required"


class TestDestinationKnowledgeBase:
    """Tests for the knowledge base as a whole."""

    def test_all_destinations_have_activities(self, knowledge_base: DestinationKnowledgeBase):
        """Every destination must have at least one activity."""
        for dest in knowledge_base.destinations:
            assert len(dest.activities) >= 1, f"{dest.name} has no activities"

    def test_all_destinations_have_multiple_activities(self, knowledge_base: DestinationKnowledgeBase):
        """Each destination should have at least 2 activities for variety."""
        for dest in knowledge_base.destinations:
            assert len(dest.activities) >= 2, f"{dest.name} has fewer than 2 activities"

    def test_knowledge_base_has_minimum_destinations(self, knowledge_base: DestinationKnowledgeBase):
        """Knowledge base should have at least 5 destinations."""
        assert len(knowledge_base.destinations) >= 5, "Need at least 5 destinations"

    def test_kitesurfing_destinations_have_wind_reliability(self, knowledge_base: DestinationKnowledgeBase):
        """All kitesurfing activities should have wind reliability data."""
        for dest in knowledge_base.destinations:
            if "kitesurfing" in dest.activities:
                kite_data = dest.activities["kitesurfing"]
                assert kite_data.reliability, f"{dest.name} kitesurfing missing reliability"
