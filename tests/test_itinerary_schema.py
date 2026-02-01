"""Tests for itinerary Pydantic schemas."""

import pytest
from pydantic import ValidationError
import uuid

from app.schemas.itinerary import (
    Activity,
    Accommodation,
    ItineraryDay,
    ItineraryProposal,
    ItineraryData,
)


class TestActivity:
    """Tests for Activity schema."""

    def test_valid_activity(self):
        """Basic activity with required fields."""
        activity = Activity(
            time="09:00",
            name="Morning surf",
            description="Beginner lesson",
            duration="2 hours",
        )
        assert activity.time == "09:00"
        assert activity.booking_required is False  # Default

    def test_activity_with_all_fields(self):
        """Activity with all optional fields."""
        activity = Activity(
            time="afternoon",
            name="Kitesurfing",
            description="Advanced session",
            duration="3 hours",
            location="Valdevaqueros Beach",
            cost_estimate="$100-150",
            booking_required=True,
        )
        assert activity.location == "Valdevaqueros Beach"
        assert activity.booking_required is True


class TestAccommodation:
    """Tests for Accommodation schema."""

    def test_valid_accommodation(self):
        """Basic accommodation with required fields."""
        acc = Accommodation(
            name="Hotel Arte Vida",
            area="Old Town",
            style="Boutique hotel",
            price_range="$120-180/night",
        )
        assert acc.name == "Hotel Arte Vida"

    def test_accommodation_with_notes(self):
        """Accommodation with notes."""
        acc = Accommodation(
            name="Surf Camp",
            area="Beach",
            style="Surf camp",
            price_range="$50-80/night",
            notes="Breakfast included",
        )
        assert acc.notes == "Breakfast included"


class TestItineraryDay:
    """Tests for ItineraryDay schema."""

    def test_valid_day(self):
        """Basic day with activities."""
        day = ItineraryDay(
            day_number=1,
            date="2026-03-15",
            title="Arrival Day",
            location="Tarifa",
            activities=[
                Activity(
                    time="evening", name="Dinner", description="Local tapas", duration="2 hours"
                )
            ],
        )
        assert day.day_number == 1
        assert len(day.activities) == 1

    def test_day_with_accommodation(self):
        """Day with accommodation."""
        day = ItineraryDay(
            day_number=1,
            date="2026-03-15",
            title="Arrival",
            location="Tarifa",
            activities=[],
            accommodation=Accommodation(
                name="Hotel", area="Center", style="Boutique", price_range="$100/night"
            ),
        )
        assert day.accommodation is not None

    def test_day_number_validation(self):
        """Day number must be >= 1."""
        with pytest.raises(ValidationError):
            ItineraryDay(
                day_number=0,
                date="2026-03-15",
                title="Invalid",
                location="Test",
                activities=[],
            )


class TestItineraryProposal:
    """Tests for ItineraryProposal schema."""

    def test_valid_proposal(self):
        """Complete proposal."""
        proposal = ItineraryProposal(
            id=str(uuid.uuid4()),
            title="Adventure Focus",
            summary="Action-packed itinerary with daily activities",
            days=[
                ItineraryDay(
                    day_number=1,
                    date="2026-03-15",
                    title="Day 1",
                    location="Tarifa",
                    activities=[],
                )
            ],
            total_budget_estimate="$1500-2000",
            highlights=["Great waves", "Wind conditions"],
            caveats=["Weather dependent"],
        )
        assert proposal.title == "Adventure Focus"


class TestItineraryData:
    """Tests for ItineraryData schema."""

    def _make_proposal(self, title: str) -> ItineraryProposal:
        """Helper to create a proposal."""
        return ItineraryProposal(
            id=str(uuid.uuid4()),
            title=title,
            summary=f"This is the {title} option",
            days=[
                ItineraryDay(
                    day_number=1,
                    date="2026-03-15",
                    title="Day 1",
                    location="Test",
                    activities=[],
                )
            ],
            total_budget_estimate="$1000",
            highlights=["Highlight"],
            caveats=["Caveat"],
        )

    def test_valid_itinerary_with_two_proposals(self):
        """Itinerary with minimum 2 proposals."""
        itinerary = ItineraryData(
            destination="Tarifa",
            start_date="2026-03-15",
            end_date="2026-03-20",
            proposals=[
                self._make_proposal("Option A"),
                self._make_proposal("Option B"),
            ],
        )
        assert len(itinerary.proposals) == 2

    def test_valid_itinerary_with_three_proposals(self):
        """Itinerary with maximum 3 proposals."""
        itinerary = ItineraryData(
            destination="Tarifa",
            start_date="2026-03-15",
            end_date="2026-03-20",
            proposals=[
                self._make_proposal("Option A"),
                self._make_proposal("Option B"),
                self._make_proposal("Option C"),
            ],
        )
        assert len(itinerary.proposals) == 3

    def test_rejects_single_proposal(self):
        """Must have at least 2 proposals."""
        with pytest.raises(ValidationError) as exc_info:
            ItineraryData(
                destination="Tarifa",
                start_date="2026-03-15",
                end_date="2026-03-20",
                proposals=[self._make_proposal("Only One")],
            )
        assert "List should have at least 2 items" in str(exc_info.value)

    def test_rejects_four_proposals(self):
        """Must have at most 3 proposals."""
        with pytest.raises(ValidationError) as exc_info:
            ItineraryData(
                destination="Tarifa",
                start_date="2026-03-15",
                end_date="2026-03-20",
                proposals=[
                    self._make_proposal("A"),
                    self._make_proposal("B"),
                    self._make_proposal("C"),
                    self._make_proposal("D"),
                ],
            )
        assert "List should have at most 3 items" in str(exc_info.value)

    def test_default_num_travelers(self):
        """Default num_travelers is 1."""
        itinerary = ItineraryData(
            destination="Tarifa",
            start_date="2026-03-15",
            end_date="2026-03-20",
            proposals=[
                self._make_proposal("A"),
                self._make_proposal("B"),
            ],
        )
        assert itinerary.num_travelers == 1

    def test_selected_proposal_optional(self):
        """selected_proposal_id is optional."""
        itinerary = ItineraryData(
            destination="Tarifa",
            start_date="2026-03-15",
            end_date="2026-03-20",
            proposals=[
                self._make_proposal("A"),
                self._make_proposal("B"),
            ],
        )
        assert itinerary.selected_proposal_id is None
