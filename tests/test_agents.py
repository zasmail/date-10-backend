"""Tests for specialized section agents."""

import pytest

from app.agents import (
    BaseAgent,
    SectionHandoff,
    SectionResult,
    CrossSectionImpact,
    FlightsAgent,
    AccommodationsAgent,
    ActivitiesAgent,
    LogisticsAgent,
)


class TestSectionHandoff:
    """Tests for SectionHandoff model."""

    def test_handoff_creation(self):
        """Test basic handoff creation."""
        handoff = SectionHandoff(
            section_type="flights",
            current_state={"outbound_flights": []},
            user_request="Find flights to Madrid",
            constraints=["Must arrive before 6pm"],
        )
        assert handoff.section_type == "flights"
        assert len(handoff.constraints) == 1
        assert handoff.user_request == "Find flights to Madrid"

    def test_handoff_with_related_sections(self):
        """Test handoff with related section data."""
        handoff = SectionHandoff(
            section_type="activities",
            current_state={"days": []},
            user_request="Plan kitesurfing activities",
            related_sections={
                "flights": {"arrival_time": "10:00"},
                "accommodations": {"location": "Tarifa Old Town"},
            },
        )
        assert "flights" in handoff.related_sections
        assert "accommodations" in handoff.related_sections

    def test_handoff_with_preferences(self):
        """Test handoff with user preferences."""
        handoff = SectionHandoff(
            section_type="accommodations",
            current_state={},
            user_request="Find boutique hotels",
            preferences={
                "style": "boutique",
                "budget_max": 500,
                "wifi_required": True,
            },
        )
        assert handoff.preferences["style"] == "boutique"

    def test_handoff_default_values(self):
        """Test handoff default values."""
        handoff = SectionHandoff(
            section_type="logistics",
            current_state={},
            user_request="Add packing list",
        )
        assert handoff.constraints == []
        assert handoff.related_sections == {}
        assert handoff.preferences is None


class TestSectionResult:
    """Tests for SectionResult model."""

    def test_result_creation(self):
        """Test basic result creation."""
        result = SectionResult(
            section_type="flights",
            updated_state={"selected_outbound_id": "fl-001"},
            changes_made=["Selected outbound flight"],
        )
        assert result.confidence == 1.0
        assert not result.needs_user_confirmation

    def test_result_with_impacts(self):
        """Test result with cross-section impacts."""
        impact = CrossSectionImpact(
            affected_section="activities",
            impact_type="arrival_time_change",
            description="Late arrival affects first day activities",
        )
        result = SectionResult(
            section_type="flights",
            updated_state={},
            changes_made=[],
            cross_section_impacts=[impact],
        )
        assert len(result.cross_section_impacts) == 1
        assert result.cross_section_impacts[0].affected_section == "activities"

    def test_result_with_confirmation(self):
        """Test result requiring user confirmation."""
        result = SectionResult(
            section_type="flights",
            updated_state={"price": 2500},
            changes_made=["Selected expensive flight"],
            needs_user_confirmation=True,
            confirmation_prompt="This flight exceeds budget. Proceed?",
        )
        assert result.needs_user_confirmation
        assert "budget" in result.confirmation_prompt

    def test_result_with_low_confidence(self):
        """Test result with low confidence."""
        result = SectionResult(
            section_type="activities",
            updated_state={"days": []},
            changes_made=["Suggested activities based on weather forecast"],
            confidence=0.7,
        )
        assert result.confidence == 0.7


class TestCrossSectionImpact:
    """Tests for CrossSectionImpact model."""

    def test_impact_creation(self):
        """Test basic impact creation."""
        impact = CrossSectionImpact(
            affected_section="activities",
            impact_type="late_arrival",
            description="Flight arrives at 11pm, first day activities affected",
        )
        assert impact.affected_section == "activities"
        assert impact.impact_type == "late_arrival"

    def test_impact_with_suggested_action(self):
        """Test impact with suggested action."""
        impact = CrossSectionImpact(
            affected_section="accommodations",
            impact_type="location_change",
            description="Activity moved to different area",
            suggested_action="Consider accommodation closer to new activity location",
        )
        assert impact.suggested_action is not None


class TestFlightsAgent:
    """Tests for FlightsAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        agent = FlightsAgent()
        assert agent.SECTION_TYPE == "flights"
        assert len(agent.TOOLS) > 0

    def test_agent_has_required_tools(self):
        """Test agent has expected tools (segment-based)."""
        agent = FlightsAgent()
        tool_names = [t["name"] for t in agent.TOOLS]
        assert "search_segment_flights" in tool_names
        assert "select_segment_flight" in tool_names
        assert "update_flights_section" in tool_names
        assert "report_cross_section_impact" in tool_names

    def test_select_flight_tool(self):
        """Test select_flight tool execution."""
        agent = FlightsAgent()
        agent.current_section_state = {
            "outbound_flights": [],
            "selected_outbound_id": None,
        }

        result = agent.execute_tool(
            "select_flight",
            {
                "flight_type": "outbound",
                "flight_id": "fl-001",
            },
        )

        assert result["status"] == "selected"
        assert agent.current_section_state["selected_outbound_id"] == "fl-001"

    def test_select_return_flight(self):
        """Test selecting return flight."""
        agent = FlightsAgent()
        agent.current_section_state = {
            "return_flights": [],
            "selected_return_id": None,
        }

        result = agent.execute_tool(
            "select_flight",
            {
                "flight_type": "return",
                "flight_id": "fl-002",
            },
        )

        assert result["status"] == "selected"
        assert agent.current_section_state["selected_return_id"] == "fl-002"

    def test_search_flights_tool(self):
        """Test search_flights tool execution."""
        agent = FlightsAgent()
        result = agent.execute_tool(
            "search_flights",
            {
                "origin": "London",
                "destination": "Madrid",
                "departure_date": "2026-03-15",
            },
        )
        assert result["status"] == "search_initiated"
        assert result["params"]["origin"] == "London"

    def test_report_cross_section_impact(self):
        """Test reporting cross-section impact."""
        agent = FlightsAgent()
        agent.cross_section_impacts = []

        result = agent.execute_tool(
            "report_cross_section_impact",
            {
                "affected_section": "activities",
                "impact_type": "late_arrival",
                "description": "Flight arrives at 11pm, first day activities may need adjustment",
            },
        )

        assert result["status"] == "impact_recorded"
        assert len(agent.cross_section_impacts) == 1
        assert agent.cross_section_impacts[0].affected_section == "activities"

    def test_update_flights_section(self):
        """Test updating flights section."""
        agent = FlightsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "update_flights_section",
            {
                "outbound_flights": [{"id": "fl-001", "price": 450}],
                "selected_outbound_id": "fl-001",
            },
        )

        assert result["status"] == "updated"
        assert len(agent.current_section_state["outbound_flights"]) == 1

    def test_unknown_tool_raises(self):
        """Test unknown tool raises ValueError."""
        agent = FlightsAgent()
        with pytest.raises(ValueError, match="Unknown tool"):
            agent.execute_tool("nonexistent_tool", {})


class TestAccommodationsAgent:
    """Tests for AccommodationsAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        agent = AccommodationsAgent()
        assert agent.SECTION_TYPE == "accommodations"

    def test_has_required_tools(self):
        """Test agent has expected tools."""
        agent = AccommodationsAgent()
        tool_names = [t["name"] for t in agent.TOOLS]
        assert "search_accommodations" in tool_names
        assert "select_accommodation" in tool_names
        assert "update_accommodations_section" in tool_names

    def test_search_accommodations_tool(self):
        """Test search_accommodations tool."""
        agent = AccommodationsAgent()
        result = agent.execute_tool(
            "search_accommodations",
            {
                "destination": "Tarifa",
                "check_in": "2026-03-15",
                "check_out": "2026-03-20",
                "style_preference": "boutique",
            },
        )
        assert result["status"] == "search_initiated"

    def test_select_accommodation_tool(self):
        """Test select_accommodation tool."""
        agent = AccommodationsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "select_accommodation",
            {
                "accommodation_name": "Hurricane Hotel",
                "dates": ["2026-03-15", "2026-03-16", "2026-03-17"],
            },
        )

        assert result["status"] == "selected"
        assert len(agent.current_section_state["nights"]) == 3

    def test_update_accommodations_section(self):
        """Test updating accommodations section."""
        agent = AccommodationsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "update_accommodations_section",
            {
                "nights": [
                    {"date": "2026-03-15", "name": "Hurricane Hotel", "area": "Beach"}
                ],
                "total_accommodation_cost": "$1,500",
            },
        )

        assert result["status"] == "updated"
        assert agent.current_section_state["total_accommodation_cost"] == "$1,500"


class TestActivitiesAgent:
    """Tests for ActivitiesAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        agent = ActivitiesAgent()
        assert agent.SECTION_TYPE == "activities"

    def test_has_required_tools(self):
        """Test agent has expected tools."""
        agent = ActivitiesAgent()
        tool_names = [t["name"] for t in agent.TOOLS]
        assert "search_operators" in tool_names
        assert "add_activity" in tool_names
        assert "update_day" in tool_names

    def test_add_activity_to_new_day(self):
        """Test adding activity creates new day."""
        agent = ActivitiesAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "add_activity",
            {
                "day_number": 1,
                "time": "09:00",
                "name": "Kitesurfing lesson",
                "description": "2-hour beginner lesson",
                "duration": "2 hours",
                "operator": "Kite School Tarifa",
            },
        )

        assert result["status"] == "added"
        assert len(agent.current_section_state["days"]) == 1
        assert len(agent.current_section_state["days"][0]["activities"]) == 1

    def test_add_activity_to_existing_day(self):
        """Test adding activity to existing day."""
        agent = ActivitiesAgent()
        agent.current_section_state = {
            "days": [
                {
                    "day_number": 1,
                    "date": "2026-03-15",
                    "title": "Day 1",
                    "location": "Tarifa",
                    "activities": [],
                    "notes": "",
                }
            ]
        }

        result = agent.execute_tool(
            "add_activity",
            {
                "day_number": 1,
                "time": "14:00",
                "name": "Beach walk",
                "description": "Explore the coastline",
                "duration": "1 hour",
            },
        )

        assert result["status"] == "added"
        assert len(agent.current_section_state["days"][0]["activities"]) == 1

    def test_update_day(self):
        """Test updating a full day."""
        agent = ActivitiesAgent()
        agent.current_section_state = {"days": []}

        result = agent.execute_tool(
            "update_day",
            {
                "day_number": 1,
                "date": "2026-03-15",
                "title": "Arrival & Orientation",
                "location": "Tarifa",
                "activities": [
                    {
                        "time": "18:00",
                        "name": "Welcome dinner",
                        "description": "Tapas at local restaurant",
                        "duration": "2 hours",
                    }
                ],
                "notes": "Rest after travel",
            },
        )

        assert result["status"] == "updated"
        assert len(agent.current_section_state["days"]) == 1
        assert agent.current_section_state["days"][0]["title"] == "Arrival & Orientation"

    def test_search_operators(self):
        """Test searching for operators."""
        agent = ActivitiesAgent()
        result = agent.execute_tool(
            "search_operators",
            {
                "destination": "Tarifa",
                "activity_type": "kitesurfing",
                "month": "March",
            },
        )
        assert result["status"] == "search_initiated"


class TestLogisticsAgent:
    """Tests for LogisticsAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        agent = LogisticsAgent()
        assert agent.SECTION_TYPE == "logistics"

    def test_has_required_tools(self):
        """Test agent has expected tools."""
        agent = LogisticsAgent()
        tool_names = [t["name"] for t in agent.TOOLS]
        assert "update_overview" in tool_names
        assert "add_transportation_note" in tool_names
        assert "add_packing_suggestion" in tool_names
        assert "add_caveat" in tool_names

    def test_add_transportation_note(self):
        """Test adding transportation note."""
        agent = LogisticsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "add_transportation_note",
            {"note": "Rent a car from Malaga airport"},
        )

        assert result["status"] == "added"
        assert len(agent.current_section_state["transportation_notes"]) == 1

    def test_add_packing_suggestion(self):
        """Test adding packing suggestion."""
        agent = LogisticsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "add_packing_suggestion",
            {"item": "Wetsuit 3/2mm"},
        )

        assert result["status"] == "added"
        assert "Wetsuit" in agent.current_section_state["packing_suggestions"][0]

    def test_set_visa_requirements(self):
        """Test setting visa requirements."""
        agent = LogisticsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "set_visa_requirements",
            {"requirements": "No visa required for US citizens (90 days)"},
        )

        assert result["status"] == "set"
        assert "No visa" in agent.current_section_state["visa_requirements"]

    def test_add_health_note(self):
        """Test adding health note."""
        agent = LogisticsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "add_health_note",
            {"note": "No vaccinations required"},
        )

        assert result["status"] == "added"
        assert len(agent.current_section_state["health_notes"]) == 1

    def test_add_caveat(self):
        """Test adding caveat."""
        agent = LogisticsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "add_caveat",
            {"caveat": "Strong winds possible in spring"},
        )

        assert result["status"] == "added"
        assert "winds" in agent.current_section_state["caveats"][0]

    def test_add_booking_requirement(self):
        """Test adding booking requirement."""
        agent = LogisticsAgent()
        agent.current_section_state = {}

        result = agent.execute_tool(
            "add_booking_requirement",
            {"requirement": "Book kite lessons 2 weeks in advance"},
        )

        assert result["status"] == "added"
        assert len(agent.current_section_state["booking_requirements"]) == 1

    def test_update_overview(self):
        """Test updating overview."""
        agent = LogisticsAgent()
        agent.overview_updates = {}

        result = agent.execute_tool(
            "update_overview",
            {
                "title": "Tarifa Kitesurfing Adventure",
                "summary": "A 5-day trip to the wind capital of Europe",
                "total_budget_estimate": "$2,500-$3,500",
            },
        )

        assert result["status"] == "overview_updated"
        assert agent.overview_updates["title"] == "Tarifa Kitesurfing Adventure"


class TestAgentSystemPrompts:
    """Tests for agent system prompts."""

    def test_flights_agent_prompt_contains_expertise(self):
        """Test flights prompt contains domain expertise."""
        agent = FlightsAgent()
        assert "flight" in agent.SYSTEM_PROMPT.lower()
        assert "cross-section" in agent.SYSTEM_PROMPT.lower()

    def test_accommodations_agent_prompt_contains_expertise(self):
        """Test accommodations prompt contains domain expertise."""
        agent = AccommodationsAgent()
        assert "accommodation" in agent.SYSTEM_PROMPT.lower()
        assert "boutique" in agent.SYSTEM_PROMPT.lower()

    def test_activities_agent_prompt_contains_expertise(self):
        """Test activities prompt contains domain expertise."""
        agent = ActivitiesAgent()
        assert "activit" in agent.SYSTEM_PROMPT.lower()
        assert "adventure" in agent.SYSTEM_PROMPT.lower()

    def test_logistics_agent_prompt_contains_expertise(self):
        """Test logistics prompt contains domain expertise."""
        agent = LogisticsAgent()
        assert "logistics" in agent.SYSTEM_PROMPT.lower()
        assert "visa" in agent.SYSTEM_PROMPT.lower()


class TestAgentBuildSystemPrompt:
    """Tests for agent system prompt building."""

    def test_build_prompt_includes_state(self):
        """Test prompt includes current state."""
        # Use AccommodationsAgent which has standard _build_system_prompt
        agent = AccommodationsAgent()
        handoff = SectionHandoff(
            section_type="accommodations",
            current_state={"nights": [{"name": "Hurricane Hotel"}]},
            user_request="Select a stay",
        )

        prompt = agent._build_system_prompt(handoff)
        assert "CURRENT SECTION STATE" in prompt
        assert "Hurricane Hotel" in prompt

    def test_build_prompt_includes_constraints(self):
        """Test prompt includes constraints."""
        # Use AccommodationsAgent which has standard _build_system_prompt
        agent = AccommodationsAgent()
        handoff = SectionHandoff(
            section_type="accommodations",
            current_state={},
            user_request="Find stays",
            constraints=["Must arrive before 6pm", "Budget under $600"],
        )

        prompt = agent._build_system_prompt(handoff)
        assert "CONSTRAINTS FROM OTHER SECTIONS" in prompt
        assert "arrive before 6pm" in prompt
        assert "Budget under $600" in prompt

    def test_build_prompt_includes_related_sections(self):
        """Test prompt includes related section data."""
        agent = ActivitiesAgent()
        handoff = SectionHandoff(
            section_type="activities",
            current_state={},
            user_request="Plan day 1",
            related_sections={
                "flights": {"arrival_time": "14:00"},
                "accommodations": {"name": "Hurricane Hotel"},
            },
        )

        prompt = agent._build_system_prompt(handoff)
        assert "RELATED SECTION DATA" in prompt
        assert "arrival_time" in prompt

    def test_build_prompt_includes_preferences(self):
        """Test prompt includes user preferences."""
        agent = AccommodationsAgent()
        handoff = SectionHandoff(
            section_type="accommodations",
            current_state={},
            user_request="Find stays",
            preferences={"style": "boutique", "wifi_required": True},
        )

        prompt = agent._build_system_prompt(handoff)
        assert "USER PREFERENCES" in prompt
        assert "boutique" in prompt
