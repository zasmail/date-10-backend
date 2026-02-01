"""Tests for operator knowledge base."""

from app.knowledge.operator_knowledge import (
    load_operator_knowledge,
    get_operators_for_destination,
    get_operators_by_activity,
    format_operators_for_prompt,
)


class TestLoadOperatorKnowledge:
    """Tests for knowledge base loading."""

    def test_load_succeeds(self):
        """Loading should return valid knowledge base."""
        kb = load_operator_knowledge()
        assert kb.version
        assert kb.last_updated
        assert len(kb.operators) > 0

    def test_cached(self):
        """Same object returned on multiple calls."""
        kb1 = load_operator_knowledge()
        kb2 = load_operator_knowledge()
        assert kb1 is kb2


class TestGetOperatorsForDestination:
    """Tests for destination filtering."""

    def test_tarifa_has_operators(self):
        """Tarifa should have operators."""
        operators = get_operators_for_destination("Tarifa")
        assert len(operators) >= 2

    def test_case_insensitive(self):
        """Lookup is case insensitive."""
        upper = get_operators_for_destination("TARIFA")
        lower = get_operators_for_destination("tarifa")
        assert len(upper) == len(lower)

    def test_unknown_destination(self):
        """Unknown destination returns empty list."""
        operators = get_operators_for_destination("Mars")
        assert len(operators) == 0


class TestGetOperatorsByActivity:
    """Tests for activity filtering."""

    def test_kitesurfing_operators(self):
        """Should find kitesurfing operators."""
        operators = get_operators_by_activity("kitesurfing")
        assert len(operators) >= 5

    def test_surfing_operators(self):
        """Should find surfing operators."""
        operators = get_operators_by_activity("surfing")
        assert len(operators) >= 3

    def test_hiking_operators(self):
        """Should find hiking operators."""
        operators = get_operators_by_activity("hiking")
        assert len(operators) >= 2


class TestFormatOperatorsForPrompt:
    """Tests for prompt formatting."""

    def test_structure(self):
        """Output should have XML structure."""
        formatted = format_operators_for_prompt()
        assert "<operator_knowledge>" in formatted
        assert "</operator_knowledge>" in formatted

    def test_destination_filter(self):
        """Should filter by destination."""
        formatted = format_operators_for_prompt("Tarifa")
        assert "Tarifa" in formatted

    def test_includes_key_fields(self):
        """Should include key operator fields."""
        formatted = format_operators_for_prompt()
        assert "Activities:" in formatted
        assert "Specialty:" in formatted
        assert "Price:" in formatted
