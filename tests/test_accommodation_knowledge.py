"""Tests for accommodation knowledge base."""

from app.knowledge.accommodation_knowledge import (
    load_accommodation_knowledge,
    get_accommodations_for_destination,
    get_accommodations_by_style,
    format_accommodations_for_prompt,
)


class TestLoadAccommodationKnowledge:
    """Tests for knowledge base loading."""

    def test_load_succeeds(self):
        """Loading should return valid knowledge base."""
        kb = load_accommodation_knowledge()
        assert kb.version
        assert kb.last_updated
        assert len(kb.accommodations) > 0

    def test_cached(self):
        """Same object returned on multiple calls."""
        kb1 = load_accommodation_knowledge()
        kb2 = load_accommodation_knowledge()
        assert kb1 is kb2


class TestGetAccommodationsForDestination:
    """Tests for destination filtering."""

    def test_tarifa_has_accommodations(self):
        """Tarifa should have accommodations."""
        accommodations = get_accommodations_for_destination("Tarifa")
        assert len(accommodations) >= 2

    def test_case_insensitive(self):
        """Lookup is case insensitive."""
        upper = get_accommodations_for_destination("TARIFA")
        lower = get_accommodations_for_destination("tarifa")
        assert len(upper) == len(lower)

    def test_unknown_destination(self):
        """Unknown destination returns empty list."""
        accommodations = get_accommodations_for_destination("Mars")
        assert len(accommodations) == 0


class TestGetAccommodationsByStyle:
    """Tests for style filtering."""

    def test_boutique_style(self):
        """Should find boutique accommodations."""
        accommodations = get_accommodations_by_style("boutique")
        assert len(accommodations) >= 3

    def test_surf_style(self):
        """Should find surf-related accommodations."""
        accommodations = get_accommodations_by_style("surf")
        assert len(accommodations) >= 2


class TestFormatAccommodationsForPrompt:
    """Tests for prompt formatting."""

    def test_structure(self):
        """Output should have XML structure."""
        formatted = format_accommodations_for_prompt()
        assert "<accommodation_knowledge>" in formatted
        assert "</accommodation_knowledge>" in formatted

    def test_destination_filter(self):
        """Should filter by destination."""
        formatted = format_accommodations_for_prompt("Tarifa")
        assert "Tarifa" in formatted

    def test_includes_key_fields(self):
        """Should include key accommodation fields."""
        formatted = format_accommodations_for_prompt()
        assert "Area:" in formatted
        assert "Style:" in formatted
        assert "Price:" in formatted
