"""Tests for refinement service tool functions."""

import pytest
import copy

from app.services.refinement_service import (
    swap_days,
    add_day,
    remove_day,
    update_activity,
    update_accommodation,
    execute_tool,
)


@pytest.fixture
def sample_proposal():
    """Sample itinerary proposal for testing."""
    return {
        "id": "test-proposal-1",
        "title": "Adventure Trip",
        "summary": "An exciting adventure",
        "days": [
            {
                "day_number": 1,
                "date": "2026-03-15",
                "title": "Arrival Day",
                "location": "Tarifa",
                "activities": [
                    {
                        "time": "14:00",
                        "name": "Hotel Check-in",
                        "description": "Check into hotel and relax",
                        "duration": "1 hour",
                        "location": "Old Town",
                    },
                    {
                        "time": "18:00",
                        "name": "Welcome Dinner",
                        "description": "Dinner at local restaurant",
                        "duration": "2 hours",
                        "location": "Beachfront",
                        "cost_estimate": "$40-60",
                    },
                ],
                "accommodation": {
                    "name": "Hotel Arte Vida",
                    "area": "Beachfront",
                    "style": "Boutique Hotel",
                    "price_range": "$120-150/night",
                    "notes": "Great views",
                },
                "notes": "Take it easy after travel",
            },
            {
                "day_number": 2,
                "date": "2026-03-16",
                "title": "Beach Day",
                "location": "Tarifa Beach",
                "activities": [
                    {
                        "time": "09:00",
                        "name": "Morning Surf",
                        "description": "Surfing lesson",
                        "duration": "3 hours",
                        "location": "Playa de los Lances",
                        "cost_estimate": "$60",
                        "booking_required": True,
                    },
                    {
                        "time": "13:00",
                        "name": "Beach Lunch",
                        "description": "Lunch at chiringuito",
                        "duration": "1.5 hours",
                        "location": "Beach",
                    },
                ],
                "accommodation": {
                    "name": "Hotel Arte Vida",
                    "area": "Beachfront",
                    "style": "Boutique Hotel",
                    "price_range": "$120-150/night",
                    "notes": "Great views",
                },
            },
            {
                "day_number": 3,
                "date": "2026-03-17",
                "title": "Kitesurf Day",
                "location": "Tarifa",
                "activities": [
                    {
                        "time": "10:00",
                        "name": "Kitesurfing",
                        "description": "Full day kitesurfing",
                        "duration": "6 hours",
                        "location": "Valdevaqueros",
                        "cost_estimate": "$150",
                        "booking_required": True,
                    },
                ],
                "accommodation": {
                    "name": "Hotel Arte Vida",
                    "area": "Beachfront",
                    "style": "Boutique Hotel",
                    "price_range": "$120-150/night",
                    "notes": "Great views",
                },
            },
            {
                "day_number": 4,
                "date": "2026-03-18",
                "title": "Departure",
                "location": "Tarifa",
                "activities": [
                    {
                        "time": "10:00",
                        "name": "Checkout",
                        "description": "Check out and head to airport",
                        "duration": "2 hours",
                    },
                ],
            },
        ],
        "total_budget_estimate": "$800-1000",
        "highlights": ["Surfing", "Kitesurfing", "Beach"],
        "caveats": ["Weather dependent"],
        "start_date": "2026-03-15",
    }


class TestSwapDays:
    """Tests for swap_days function."""

    def test_swap_adjacent_days(self, sample_proposal):
        """Swap two adjacent days."""
        result = swap_days(sample_proposal, 2, 3)

        # Day 2 should now have kitesurf content
        assert result["days"][1]["title"] == "Kitesurf Day"
        # Day 3 should now have beach content
        assert result["days"][2]["title"] == "Beach Day"
        # Day numbers should be renumbered
        assert result["days"][1]["day_number"] == 2
        assert result["days"][2]["day_number"] == 3
        # Dates should be updated
        assert result["days"][1]["date"] == "2026-03-16"
        assert result["days"][2]["date"] == "2026-03-17"

    def test_swap_non_adjacent_days(self, sample_proposal):
        """Swap two non-adjacent days."""
        result = swap_days(sample_proposal, 1, 4)

        assert result["days"][0]["title"] == "Departure"
        assert result["days"][3]["title"] == "Arrival Day"
        # Day numbers renumbered correctly
        assert result["days"][0]["day_number"] == 1
        assert result["days"][3]["day_number"] == 4

    def test_swap_same_day_noop(self, sample_proposal):
        """Swapping same day should keep structure."""
        result = swap_days(sample_proposal, 2, 2)
        assert result["days"][1]["title"] == "Beach Day"

    def test_swap_out_of_range(self, sample_proposal):
        """Out of range day numbers should raise error."""
        with pytest.raises(ValueError, match="out of range"):
            swap_days(sample_proposal, 0, 2)

        with pytest.raises(ValueError, match="out of range"):
            swap_days(sample_proposal, 1, 10)

    def test_swap_preserves_other_days(self, sample_proposal):
        """Swapping should not affect other days."""
        result = swap_days(sample_proposal, 2, 3)

        # Day 1 and 4 unchanged (except numbering/dates)
        assert result["days"][0]["title"] == "Arrival Day"
        assert result["days"][3]["title"] == "Departure"


class TestAddDay:
    """Tests for add_day function."""

    def test_add_rest_day_after_kitesurf(self, sample_proposal):
        """Add a rest day after an activity-heavy day."""
        result = add_day(
            sample_proposal,
            after_day=3,
            title="Rest & Recovery",
            location="Tarifa",
            activities=[
                {
                    "time": "10:00",
                    "name": "Sleep In",
                    "description": "Late morning rest",
                    "duration": "3 hours",
                },
                {
                    "time": "14:00",
                    "name": "Spa",
                    "description": "Massage and relaxation",
                    "duration": "2 hours",
                    "cost_estimate": "$80",
                },
            ],
            notes="Recovery day",
        )

        # Should now have 5 days
        assert len(result["days"]) == 5
        # New day at position 3 (0-indexed)
        assert result["days"][3]["title"] == "Rest & Recovery"
        assert result["days"][3]["day_number"] == 4
        # Departure moved to day 5
        assert result["days"][4]["title"] == "Departure"
        assert result["days"][4]["day_number"] == 5
        # New day should inherit accommodation from previous
        assert result["days"][3]["accommodation"]["name"] == "Hotel Arte Vida"

    def test_add_day_at_start(self, sample_proposal):
        """Add a day at the beginning."""
        result = add_day(
            sample_proposal,
            after_day=0,
            title="Pre-trip Day",
            location="Madrid",
            activities=[
                {
                    "time": "18:00",
                    "name": "Evening Flight",
                    "description": "Fly to Madrid",
                    "duration": "2 hours",
                },
            ],
        )

        assert len(result["days"]) == 5
        assert result["days"][0]["title"] == "Pre-trip Day"
        assert result["days"][0]["day_number"] == 1
        assert result["days"][1]["title"] == "Arrival Day"
        assert result["days"][1]["day_number"] == 2

    def test_add_day_with_custom_accommodation(self, sample_proposal):
        """Add a day with different accommodation."""
        result = add_day(
            sample_proposal,
            after_day=2,
            title="Mountain Excursion",
            location="Grazalema",
            activities=[
                {
                    "time": "09:00",
                    "name": "Hiking",
                    "description": "Mountain trail hike",
                    "duration": "6 hours",
                },
            ],
            accommodation={
                "name": "Mountain Lodge",
                "area": "Grazalema",
                "style": "Rural Hotel",
                "price_range": "$80-100/night",
                "notes": "Rustic charm",
            },
        )

        assert result["days"][2]["accommodation"]["name"] == "Mountain Lodge"

    def test_add_day_updates_end_date(self, sample_proposal):
        """Adding a day should update end_date."""
        original_end = sample_proposal.get("end_date", sample_proposal["days"][-1]["date"])
        result = add_day(
            sample_proposal,
            after_day=4,
            title="Extra Day",
            location="Tarifa",
            activities=[{"time": "10:00", "name": "Free Time", "description": "Explore", "duration": "all day"}],
        )

        # End date should be later
        assert result["end_date"] == "2026-03-19"

    def test_add_day_invalid_position(self, sample_proposal):
        """Invalid position should raise error."""
        with pytest.raises(ValueError, match="out of range"):
            add_day(
                sample_proposal,
                after_day=10,
                title="Invalid",
                location="Nowhere",
                activities=[],
            )


class TestRemoveDay:
    """Tests for remove_day function."""

    def test_remove_middle_day(self, sample_proposal):
        """Remove a day from the middle."""
        result = remove_day(sample_proposal, day_number=2)

        assert len(result["days"]) == 3
        # Day 1 unchanged
        assert result["days"][0]["title"] == "Arrival Day"
        # Old day 3 is now day 2
        assert result["days"][1]["title"] == "Kitesurf Day"
        assert result["days"][1]["day_number"] == 2
        assert result["days"][1]["date"] == "2026-03-16"
        # Old day 4 is now day 3
        assert result["days"][2]["title"] == "Departure"
        assert result["days"][2]["day_number"] == 3

    def test_remove_first_day(self, sample_proposal):
        """Remove the first day."""
        result = remove_day(sample_proposal, day_number=1)

        assert len(result["days"]) == 3
        assert result["days"][0]["title"] == "Beach Day"
        assert result["days"][0]["day_number"] == 1

    def test_remove_last_day(self, sample_proposal):
        """Remove the last day."""
        result = remove_day(sample_proposal, day_number=4)

        assert len(result["days"]) == 3
        assert result["days"][-1]["title"] == "Kitesurf Day"
        assert result["end_date"] == "2026-03-17"

    def test_remove_only_day_raises_error(self, sample_proposal):
        """Cannot remove the only day."""
        single_day_proposal = copy.deepcopy(sample_proposal)
        single_day_proposal["days"] = [sample_proposal["days"][0]]

        with pytest.raises(ValueError, match="Cannot remove the only day"):
            remove_day(single_day_proposal, day_number=1)

    def test_remove_invalid_day(self, sample_proposal):
        """Invalid day number should raise error."""
        with pytest.raises(ValueError, match="out of range"):
            remove_day(sample_proposal, day_number=0)

        with pytest.raises(ValueError, match="out of range"):
            remove_day(sample_proposal, day_number=10)


class TestUpdateActivity:
    """Tests for update_activity function."""

    def test_update_activity_time(self, sample_proposal):
        """Update activity timing."""
        result = update_activity(
            sample_proposal,
            day_number=2,
            activity_index=0,
            action="update",
            new_activity={"time": "08:00"},
        )

        # Time updated
        assert result["days"][1]["activities"][0]["time"] == "08:00"
        # Other fields preserved
        assert result["days"][1]["activities"][0]["name"] == "Morning Surf"

    def test_replace_activity(self, sample_proposal):
        """Replace an activity entirely."""
        result = update_activity(
            sample_proposal,
            day_number=2,
            activity_index=0,
            action="replace",
            new_activity={
                "time": "10:00",
                "name": "Yoga Session",
                "description": "Beach yoga",
                "duration": "1.5 hours",
                "location": "Beach",
                "cost_estimate": "$25",
            },
        )

        assert result["days"][1]["activities"][0]["name"] == "Yoga Session"
        assert result["days"][1]["activities"][0]["duration"] == "1.5 hours"

    def test_remove_activity(self, sample_proposal):
        """Remove an activity."""
        original_count = len(sample_proposal["days"][1]["activities"])
        result = update_activity(
            sample_proposal,
            day_number=2,
            activity_index=1,
            action="remove",
        )

        assert len(result["days"][1]["activities"]) == original_count - 1
        # Beach Lunch removed, only Morning Surf remains
        assert result["days"][1]["activities"][0]["name"] == "Morning Surf"

    def test_update_invalid_day(self, sample_proposal):
        """Invalid day number should raise error."""
        with pytest.raises(ValueError, match="out of range"):
            update_activity(
                sample_proposal,
                day_number=10,
                activity_index=0,
                action="update",
                new_activity={"time": "10:00"},
            )

    def test_update_invalid_activity_index(self, sample_proposal):
        """Invalid activity index should raise error."""
        with pytest.raises(ValueError, match="out of range"):
            update_activity(
                sample_proposal,
                day_number=2,
                activity_index=10,
                action="update",
                new_activity={"time": "10:00"},
            )

    def test_update_without_new_activity(self, sample_proposal):
        """Update/replace without new_activity should raise error."""
        with pytest.raises(ValueError, match="new_activity required"):
            update_activity(
                sample_proposal,
                day_number=2,
                activity_index=0,
                action="update",
            )


class TestUpdateAccommodation:
    """Tests for update_accommodation function."""

    def test_update_accommodation_single_day(self, sample_proposal):
        """Update accommodation for one day."""
        result = update_accommodation(
            sample_proposal,
            day_number=2,
            accommodation={
                "name": "Budget Hostel",
                "area": "Old Town",
                "style": "Hostel",
                "price_range": "$30-50/night",
                "notes": "Social atmosphere",
            },
        )

        assert result["days"][1]["accommodation"]["name"] == "Budget Hostel"
        # Other days unchanged
        assert result["days"][0]["accommodation"]["name"] == "Hotel Arte Vida"
        assert result["days"][2]["accommodation"]["name"] == "Hotel Arte Vida"

    def test_update_accommodation_consecutive(self, sample_proposal):
        """Update accommodation for all consecutive days with same hotel."""
        result = update_accommodation(
            sample_proposal,
            day_number=2,
            accommodation={
                "name": "Luxury Resort",
                "area": "Beachfront",
                "style": "Resort",
                "price_range": "$250-300/night",
                "notes": "All inclusive",
            },
            apply_to_consecutive=True,
        )

        # Days 1, 2, 3 all had Hotel Arte Vida
        assert result["days"][0]["accommodation"]["name"] == "Luxury Resort"
        assert result["days"][1]["accommodation"]["name"] == "Luxury Resort"
        assert result["days"][2]["accommodation"]["name"] == "Luxury Resort"
        # Day 4 has no accommodation
        assert result["days"][3].get("accommodation") is None

    def test_update_accommodation_invalid_day(self, sample_proposal):
        """Invalid day should raise error."""
        with pytest.raises(ValueError, match="out of range"):
            update_accommodation(
                sample_proposal,
                day_number=10,
                accommodation={
                    "name": "Test",
                    "area": "Test",
                    "style": "Test",
                    "price_range": "$0",
                },
            )


class TestExecuteTool:
    """Tests for execute_tool router function."""

    def test_execute_swap_days(self, sample_proposal):
        """Execute swap_days through router."""
        result = execute_tool(
            "swap_days",
            {"day_a": 2, "day_b": 3},
            sample_proposal,
        )
        assert result["days"][1]["title"] == "Kitesurf Day"

    def test_execute_add_day(self, sample_proposal):
        """Execute add_day through router."""
        result = execute_tool(
            "add_day",
            {
                "after_day": 1,
                "title": "New Day",
                "location": "Tarifa",
                "activities": [{"time": "10:00", "name": "Activity", "description": "Fun", "duration": "2 hours"}],
            },
            sample_proposal,
        )
        assert len(result["days"]) == 5

    def test_execute_remove_day(self, sample_proposal):
        """Execute remove_day through router."""
        result = execute_tool(
            "remove_day",
            {"day_number": 2},
            sample_proposal,
        )
        assert len(result["days"]) == 3

    def test_execute_update_activity(self, sample_proposal):
        """Execute update_activity through router."""
        result = execute_tool(
            "update_activity",
            {
                "day_number": 2,
                "activity_index": 0,
                "action": "update",
                "new_activity": {"time": "07:00"},
            },
            sample_proposal,
        )
        assert result["days"][1]["activities"][0]["time"] == "07:00"

    def test_execute_update_accommodation(self, sample_proposal):
        """Execute update_accommodation through router."""
        result = execute_tool(
            "update_accommodation",
            {
                "day_number": 1,
                "accommodation": {
                    "name": "New Hotel",
                    "area": "Center",
                    "style": "Modern",
                    "price_range": "$100/night",
                },
            },
            sample_proposal,
        )
        assert result["days"][0]["accommodation"]["name"] == "New Hotel"

    def test_execute_unknown_tool(self, sample_proposal):
        """Unknown tool should raise error."""
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool("unknown_tool", {}, sample_proposal)
