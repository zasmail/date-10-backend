"""Tests for accommodation Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.accommodation import (
    AccommodationOption,
    AccommodationRecommendations,
)


class TestAccommodationOption:
    """Tests for AccommodationOption schema."""

    def test_valid_option(self):
        """Basic option with required fields."""
        option = AccommodationOption(
            name="Hotel Test",
            destination="Tarifa",
            area="Old Town",
            style="Boutique",
            price_range="$100-150/night",
            why_recommended="Great fit",
        )
        assert option.name == "Hotel Test"
        assert option.highlights == []  # Default

    def test_option_with_all_fields(self):
        """Option with all fields."""
        option = AccommodationOption(
            name="Hotel Test",
            destination="Tarifa",
            area="Old Town",
            style="Boutique",
            price_range="$100-150/night",
            highlights=["Pool", "Beach"],
            best_for=["Couples"],
            booking_notes="Book early",
            why_recommended="Perfect match",
        )
        assert len(option.highlights) == 2
        assert option.booking_notes == "Book early"


class TestAccommodationRecommendations:
    """Tests for AccommodationRecommendations schema."""

    def _make_option(self, name: str) -> AccommodationOption:
        return AccommodationOption(
            name=name,
            destination="Tarifa",
            area="Test",
            style="Boutique",
            price_range="$100/night",
            why_recommended="Test",
        )

    def test_valid_recommendations(self):
        """Valid recommendations with 1+ options."""
        recs = AccommodationRecommendations(
            destination="Tarifa",
            recommendations=[self._make_option("Hotel A")],
            summary="Found options",
        )
        assert len(recs.recommendations) == 1

    def test_max_recommendations(self):
        """Can have up to 5 recommendations."""
        recs = AccommodationRecommendations(
            destination="Tarifa",
            recommendations=[self._make_option(f"Hotel {i}") for i in range(5)],
            summary="Found options",
        )
        assert len(recs.recommendations) == 5

    def test_rejects_too_many(self):
        """Rejects more than 5 recommendations."""
        with pytest.raises(ValidationError):
            AccommodationRecommendations(
                destination="Tarifa",
                recommendations=[self._make_option(f"Hotel {i}") for i in range(6)],
                summary="Too many",
            )

    def test_rejects_empty(self):
        """Rejects empty recommendations."""
        with pytest.raises(ValidationError):
            AccommodationRecommendations(
                destination="Tarifa",
                recommendations=[],
                summary="None",
            )
