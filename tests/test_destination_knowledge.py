"""Tests for destination knowledge loading and formatting."""

from app.knowledge.destination_knowledge import (
    format_knowledge_for_prompt,
    get_destinations_for_month,
    load_knowledge_base,
)
from app.knowledge.schemas import DestinationKnowledgeBase


class TestLoadKnowledgeBase:
    """Tests for knowledge base loading."""

    def test_load_succeeds(self):
        """Loading should return a valid DestinationKnowledgeBase."""
        kb = load_knowledge_base()
        assert isinstance(kb, DestinationKnowledgeBase)
        assert kb.version
        assert kb.last_updated
        assert len(kb.destinations) > 0

    def test_cached(self):
        """Same object should be returned on multiple calls (cached)."""
        kb1 = load_knowledge_base()
        kb2 = load_knowledge_base()
        assert kb1 is kb2, "Knowledge base should be cached"


class TestGetDestinationsForMonth:
    """Tests for month-based destination filtering."""

    def test_march_returns_destinations(self):
        """March should return destinations with activities in season."""
        march_dests = get_destinations_for_month(3)
        assert len(march_dests) > 0, "Should have destinations for March"

        # Verify all returned destinations have at least one March activity
        for dest in march_dests:
            has_march_activity = any(3 in a.season for a in dest.activities.values())
            assert has_march_activity, f"{dest.name} has no March activities"

    def test_filters_correctly(self):
        """Destinations not in season should be filtered out."""
        kb = load_knowledge_base()

        # Find a month where not all destinations are in season
        for month in range(1, 13):
            dests_for_month = get_destinations_for_month(month)
            if len(dests_for_month) < len(kb.destinations):
                # Found a month that filters some destinations
                filtered_names = {d.name for d in dests_for_month}
                all_names = {d.name for d in kb.destinations}
                excluded_names = all_names - filtered_names

                # Verify excluded destinations don't have activities in this month
                for dest in kb.destinations:
                    if dest.name in excluded_names:
                        for activity_data in dest.activities.values():
                            assert (
                                month not in activity_data.season
                            ), f"{dest.name} should be excluded for month {month}"
                break

    def test_all_months_return_at_least_one(self):
        """Every month should have at least one destination available."""
        for month in range(1, 13):
            dests = get_destinations_for_month(month)
            assert len(dests) >= 1, f"No destinations for month {month}"


class TestFormatKnowledgeForPrompt:
    """Tests for knowledge formatting."""

    def test_structure_has_xml_tags(self):
        """Output should have proper XML structure."""
        formatted = format_knowledge_for_prompt()
        assert "<destination_knowledge>" in formatted
        assert "</destination_knowledge>" in formatted

    def test_includes_destination_names(self):
        """Output should include all destination names."""
        kb = load_knowledge_base()
        formatted = format_knowledge_for_prompt()

        for dest in kb.destinations:
            assert dest.name in formatted, f"{dest.name} missing from formatted output"

    def test_includes_activity_names(self):
        """Output should include activity names."""
        formatted = format_knowledge_for_prompt()

        # Check for known activities
        assert "kitesurfing" in formatted.lower()
        assert "surfing" in formatted.lower()

    def test_includes_seasonality_as_month_names(self):
        """Output should contain month names, not just numbers."""
        formatted = format_knowledge_for_prompt()

        # Should have month names
        month_names = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]

        found_months = [m for m in month_names if m in formatted]
        assert len(found_months) >= 6, "Should have multiple month names in output"

    def test_includes_reliability_for_wind_sports(self):
        """Wind reliability percentages should appear in output."""
        formatted = format_knowledge_for_prompt()

        # Should have reliability percentages
        assert "%" in formatted, "Should include reliability percentages"

    def test_includes_all_sections(self):
        """Output should include all major sections."""
        formatted = format_knowledge_for_prompt()

        assert "<activities>" in formatted
        assert "<climate>" in formatted
        assert "<logistics>" in formatted
        assert "<accommodation>" in formatted
        assert "<vibe>" in formatted
        assert "<why_go>" in formatted
        assert "<why_skip>" in formatted

    def test_custom_destinations_list(self):
        """Should format only specified destinations when passed."""
        kb = load_knowledge_base()
        subset = kb.destinations[:2]  # First two destinations

        formatted = format_knowledge_for_prompt(subset)

        # Should have the two destinations
        for dest in subset:
            assert dest.name in formatted

        # Should not have the third destination (if there is one)
        if len(kb.destinations) > 2:
            assert kb.destinations[2].name not in formatted
