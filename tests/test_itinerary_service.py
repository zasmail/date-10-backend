"""Tests for itinerary service."""

from app.services.itinerary_service import GENERATE_ITINERARY_TOOL


class TestGenerateItineraryTool:
    """Tests for the Claude tool definition."""

    def test_tool_has_required_fields(self):
        """Tool definition has name, description, input_schema."""
        assert "name" in GENERATE_ITINERARY_TOOL
        assert "description" in GENERATE_ITINERARY_TOOL
        assert "input_schema" in GENERATE_ITINERARY_TOOL

    def test_tool_name(self):
        """Tool is named correctly."""
        assert GENERATE_ITINERARY_TOOL["name"] == "generate_itinerary"

    def test_tool_schema_is_object(self):
        """Input schema is an object type."""
        assert GENERATE_ITINERARY_TOOL["input_schema"]["type"] == "object"

    def test_required_fields(self):
        """Required fields are specified."""
        required = GENERATE_ITINERARY_TOOL["input_schema"]["required"]
        assert "destination" in required
        assert "start_date" in required
        assert "end_date" in required
        assert "proposals" in required

    def test_proposals_array_constraints(self):
        """Proposals array has min/max items."""
        proposals = GENERATE_ITINERARY_TOOL["input_schema"]["properties"]["proposals"]
        assert proposals["type"] == "array"
        assert proposals["minItems"] == 2
        assert proposals["maxItems"] == 3

    def test_proposal_has_days(self):
        """Proposal schema includes days array."""
        proposal_schema = GENERATE_ITINERARY_TOOL["input_schema"]["properties"]["proposals"]["items"]
        assert "days" in proposal_schema["properties"]
        assert proposal_schema["properties"]["days"]["type"] == "array"

    def test_day_has_activities(self):
        """Day schema includes activities array."""
        day_schema = GENERATE_ITINERARY_TOOL["input_schema"]["properties"]["proposals"]["items"][
            "properties"
        ]["days"]["items"]
        assert "activities" in day_schema["properties"]
        assert day_schema["properties"]["activities"]["type"] == "array"

    def test_tool_description_mentions_proposals(self):
        """Tool description mentions generating 2-3 proposals."""
        description = GENERATE_ITINERARY_TOOL["description"]
        assert "2-3" in description
        assert "proposals" in description.lower()
