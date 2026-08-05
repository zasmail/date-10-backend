"""Integration tests for FlightsAgent with multi-segment support."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.agents.flights_agent import FlightsAgent
from app.agents.base_agent import SectionHandoff
from app.schemas.flight import (
    FlightSearchResponse,
    FlightOption,
    FlightSegmentResult,
    FlightLeg,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def flights_agent():
    return FlightsAgent()


@pytest.fixture
def mock_flight_response():
    """Create a realistic flight search response."""
    return FlightSearchResponse(
        search_id="test-search-123",
        searched_at=datetime.utcnow(),
        origin="JFK",
        destination="AGP",
        options=[
            FlightOption(
                id="opt-1",
                total_price=650.0,
                currency="USD",
                price_per_person=650.0,
                segments=[
                    FlightSegmentResult(
                        segment_id=1,
                        flights=[
                            FlightLeg(
                                departure_airport="JFK",
                                arrival_airport="AGP",
                                departure_time="2026-05-15T08:00:00",
                                arrival_time="2026-05-15T20:30:00",
                                airline="IB",
                                flight_number="IB6250",
                                duration_minutes=510,
                                operating_airline=None,
                            )
                        ],
                    )
                ],
                is_virtual_interlining=False,
                warnings=[],
                booking_url="https://book.example.com/opt-1",
            ),
            FlightOption(
                id="opt-2",
                total_price=720.0,
                currency="USD",
                price_per_person=720.0,
                segments=[
                    FlightSegmentResult(
                        segment_id=1,
                        flights=[
                            FlightLeg(
                                departure_airport="JFK",
                                arrival_airport="MAD",
                                departure_time="2026-05-15T10:00:00",
                                arrival_time="2026-05-15T22:00:00",
                                airline="AA",
                                flight_number="AA100",
                                duration_minutes=480,
                                operating_airline=None,
                            ),
                            FlightLeg(
                                departure_airport="MAD",
                                arrival_airport="AGP",
                                departure_time="2026-05-15T23:30:00",
                                arrival_time="2026-05-16T00:30:00",
                                airline="IB",
                                flight_number="IB3850",
                                duration_minutes=60,
                                operating_airline=None,
                            ),
                        ],
                    )
                ],
                is_virtual_interlining=False,
                warnings=[],
                booking_url=None,
            ),
        ],
        cheapest_price=650.0,
        price_range="$650-$720",
    )


@pytest.fixture
def generation_handoff():
    """Handoff for initial generation (empty state)."""
    return SectionHandoff(
        section_type="flights",
        user_request="Find flights to Tarifa",
        current_state={},
        constraints=["is_generation"],
        related_sections={
            "overview": {
                "destination": "Tarifa",
                "start_date": "2026-05-15",
                "end_date": "2026-05-22",
                "num_travelers": 2,
            }
        },
        preferences={"cabin_class": "E"},
    )


@pytest.fixture
def refinement_handoff():
    """Handoff for refinement (existing segments)."""
    return SectionHandoff(
        section_type="flights",
        user_request="Find cheaper options for segment 1",
        current_state={
            "segments": [
                {
                    "id": 1,
                    "origin": "JFK",
                    "destination": "AGP",
                    "date": "2026-05-15",
                    "options": [{"id": "opt-1", "total_price": 650}],
                    "selected_option_id": "opt-1",
                }
            ]
        },
        constraints=[],
        related_sections={},
        preferences={},
    )


# ============================================================================
# Mode Detection Tests
# ============================================================================


class TestModeDetection:
    def test_generation_mode_with_constraint(self, flights_agent, generation_handoff):
        """is_generation constraint triggers generation mode."""
        assert flights_agent._is_generation_mode(generation_handoff) is True

    def test_generation_mode_with_empty_segments(self, flights_agent):
        """Empty segments triggers generation mode."""
        handoff = SectionHandoff(
            section_type="flights",
            user_request="Find flights",
            current_state={},
            constraints=[],
            related_sections={},
            preferences={},
        )
        assert flights_agent._is_generation_mode(handoff) is True

    def test_refinement_mode_with_existing_segments(
        self, flights_agent, refinement_handoff
    ):
        """Existing segments triggers refinement mode."""
        assert flights_agent._is_generation_mode(refinement_handoff) is False


# ============================================================================
# Prompt Selection Tests
# ============================================================================


class TestPromptSelection:
    def test_generation_prompt_for_new_flights(
        self, flights_agent, generation_handoff
    ):
        """Generation mode uses FLIGHTS_GENERATION_PROMPT."""
        prompt = flights_agent._build_system_prompt(generation_handoff)
        assert "CRITICAL REQUIREMENTS" in prompt
        assert "search_segment_flights" in prompt

    def test_refinement_prompt_for_existing_flights(
        self, flights_agent, refinement_handoff
    ):
        """Refinement mode uses FLIGHTS_AGENT_PROMPT."""
        prompt = flights_agent._build_system_prompt(refinement_handoff)
        # Refinement prompt should NOT have generation markers
        assert "CRITICAL REQUIREMENTS" not in prompt or "refine" in prompt.lower()

    def test_prompt_includes_overview_context(
        self, flights_agent, generation_handoff
    ):
        """Prompt includes itinerary context from overview."""
        prompt = flights_agent._build_system_prompt(generation_handoff)
        assert "Tarifa" in prompt
        assert "2026-05-15" in prompt


# ============================================================================
# API Conversion Tests
# ============================================================================


class TestApiConversion:
    def test_convert_api_response_to_segment_options(
        self, flights_agent, mock_flight_response
    ):
        """Converts Trip Ninja response to FlightSegmentOption format."""
        options = flights_agent._convert_api_to_segment_options(
            mock_flight_response.options
        )

        assert len(options) == 2

        # First option - direct flight
        opt1 = options[0]
        assert opt1["id"] == "opt-1"
        assert opt1["total_price"] == 650.0
        assert len(opt1["legs"]) == 1
        assert opt1["legs"][0]["airline"] == "IB"

        # Second option - connecting flight
        opt2 = options[1]
        assert opt2["id"] == "opt-2"
        assert len(opt2["legs"]) == 2
        assert opt2["legs"][0]["arrival_airport"] == "MAD"
        assert opt2["legs"][1]["departure_airport"] == "MAD"

    def test_conversion_preserves_virtual_interlining_flag(self, flights_agent):
        """Virtual interlining flag is preserved in conversion."""
        vi_option = FlightOption(
            id="vi-1",
            total_price=500.0,
            currency="USD",
            price_per_person=500.0,
            segments=[],
            is_virtual_interlining=True,
            warnings=["Self-transfer required"],
            booking_url=None,
        )
        converted = flights_agent._convert_api_to_segment_options([vi_option])
        assert converted[0]["is_virtual_interlining"] is True
        assert "Self-transfer" in converted[0]["warnings"][0]


# ============================================================================
# Price Calculation Tests
# ============================================================================


class TestPriceCalculation:
    def test_calculate_price_range_from_segments(self, flights_agent):
        """Price range calculated from min/max across segments."""
        segments = [
            {
                "id": 1,
                "options": [
                    {"id": "a", "total_price": 500},
                    {"id": "b", "total_price": 700},
                ],
            },
            {
                "id": 2,
                "options": [
                    {"id": "c", "total_price": 400},
                    {"id": "d", "total_price": 600},
                ],
            },
        ]
        price_range = flights_agent._calculate_price_range(segments)
        # Min: 500 + 400 = 900, Max: 700 + 600 = 1300
        assert price_range == "$900-$1300"

    def test_calculate_total_price_from_selections(self, flights_agent):
        """Total price calculated from selected options."""
        segments = [
            {
                "id": 1,
                "selected_option_id": "a",
                "options": [
                    {"id": "a", "total_price": 500},
                    {"id": "b", "total_price": 700},
                ],
            },
            {
                "id": 2,
                "selected_option_id": "c",
                "options": [
                    {"id": "c", "total_price": 400},
                ],
            },
        ]
        total = flights_agent._calculate_total_price(segments)
        assert total == 900.0

    def test_calculate_total_price_uses_best_option_as_fallback(self, flights_agent):
        """Total uses best_option_id if no selection."""
        segments = [
            {
                "id": 1,
                "best_option_id": "a",
                "options": [{"id": "a", "total_price": 650}],
            },
        ]
        total = flights_agent._calculate_total_price(segments)
        assert total == 650.0


# ============================================================================
# Tool Execution Tests (Async)
# ============================================================================


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_search_segment_flights_calls_api(
        self, flights_agent, mock_flight_response, mocker
    ):
        """search_segment_flights tool calls real flight_service."""
        mock_search = mocker.patch(
            "app.services.flight_service.search_flights",
            return_value=mock_flight_response,
        )

        result = await flights_agent.execute_tool_async(
            "search_segment_flights",
            {
                "segment_id": 1,
                "origin": "New York",
                "destination": "Malaga",
                "date": "2026-05-15",
                "num_travelers": 1,
            },
        )

        assert mock_search.called
        assert result["status"] == "search_complete"
        assert result["segment_id"] == 1
        assert result["options_count"] == 2
        assert result["best_option_id"] == "opt-1"  # Cheapest auto-selected

    @pytest.mark.asyncio
    async def test_select_segment_flight_updates_state(self, flights_agent):
        """select_segment_flight updates selected_option_id for segment."""
        flights_agent.current_section_state = {
            "segments": [
                {
                    "id": 1,
                    "options": [
                        {"id": "opt-1", "total_price": 500},
                        {"id": "opt-2", "total_price": 600},
                    ],
                    "selected_option_id": None,
                },
                {
                    "id": 2,
                    "options": [{"id": "opt-3", "total_price": 400}],
                    "selected_option_id": None,
                },
            ]
        }

        result = await flights_agent.execute_tool_async(
            "select_segment_flight",
            {
                "segment_id": 1,
                "option_id": "opt-2",
            },
        )

        assert result["status"] == "selected"
        assert (
            flights_agent.current_section_state["segments"][0]["selected_option_id"]
            == "opt-2"
        )
        assert (
            flights_agent.current_section_state["segments"][1]["selected_option_id"]
            is None
        )

    @pytest.mark.asyncio
    async def test_update_flights_section_calculates_totals(self, flights_agent):
        """update_flights_section calculates price_range and total_price."""
        segments = [
            {
                "id": 1,
                "origin": "JFK",
                "destination": "AGP",
                "best_option_id": "opt-1",
                "options": [
                    {"id": "opt-1", "total_price": 650.0},
                    {"id": "opt-2", "total_price": 720.0},
                ],
            },
            {
                "id": 2,
                "origin": "AGP",
                "destination": "JFK",
                "best_option_id": "opt-3",
                "options": [
                    {"id": "opt-3", "total_price": 600.0},
                ],
            },
        ]

        result = await flights_agent.execute_tool_async(
            "update_flights_section",
            {
                "segments": segments,
            },
        )

        assert result["status"] == "updated"
        assert result["segment_count"] == 2
        assert result["price_range"] == "$1250-$1320"  # 650+600 to 720+600
        assert result["total_price"] == 1250.0  # best options: 650 + 600
        assert "searched_at" in flights_agent.current_section_state

    @pytest.mark.asyncio
    async def test_report_cross_section_impact(self, flights_agent):
        """Cross-section impacts are recorded."""
        result = await flights_agent.execute_tool_async(
            "report_cross_section_impact",
            {
                "affected_section": "activities",
                "impact_type": "arrival_time",
                "description": "Flight arrives at 20:30, affecting Day 1 evening plans",
                "suggested_action": "Move evening activity to Day 2",
            },
        )

        assert result["status"] == "impact_recorded"
        assert len(flights_agent.cross_section_impacts) == 1
        assert flights_agent.cross_section_impacts[0].affected_section == "activities"


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestSchemaValidation:
    def test_flight_segment_date_validation(self):
        """FlightSegment validates date format."""
        from app.schemas.itinerary_sections import FlightSegment

        # Valid date
        seg = FlightSegment(id=1, origin="JFK", destination="AGP", date="2026-05-15")
        assert seg.date == "2026-05-15"

        # Invalid date format
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            FlightSegment(id=1, origin="JFK", destination="AGP", date="May 15, 2026")

    def test_flights_section_get_selected_total(self):
        """FlightsSection.get_selected_total calculates from selections."""
        from app.schemas.itinerary_sections import (
            FlightsSection,
            FlightSegment,
            FlightSegmentOption,
        )

        section = FlightsSection(
            segments=[
                FlightSegment(
                    id=1,
                    origin="JFK",
                    destination="AGP",
                    date="2026-05-15",
                    options=[
                        FlightSegmentOption(
                            id="opt-1", legs=[], total_price=650.0, price_per_person=650.0
                        ),
                        FlightSegmentOption(
                            id="opt-2", legs=[], total_price=720.0, price_per_person=720.0
                        ),
                    ],
                    selected_option_id="opt-1",
                ),
                FlightSegment(
                    id=2,
                    origin="AGP",
                    destination="JFK",
                    date="2026-05-22",
                    options=[
                        FlightSegmentOption(
                            id="opt-3", legs=[], total_price=600.0, price_per_person=600.0
                        ),
                    ],
                    selected_option_id="opt-3",
                ),
            ]
        )

        assert section.get_selected_total() == 1250.0  # 650 + 600

    def test_flights_section_no_selections_returns_none(self):
        """get_selected_total returns None when no selections."""
        from app.schemas.itinerary_sections import FlightsSection, FlightSegment

        section = FlightsSection(
            segments=[
                FlightSegment(
                    id=1, origin="JFK", destination="AGP", date="2026-05-15", options=[]
                ),
            ]
        )

        assert section.get_selected_total() is None


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    def test_empty_segments_price_range(self, flights_agent):
        """Price range with no segments returns $0."""
        price_range = flights_agent._calculate_price_range([])
        assert price_range == "$0"

    def test_empty_options_in_segment(self, flights_agent):
        """Segment with no options doesn't affect price calculation."""
        segments = [
            {"id": 1, "options": []},
            {"id": 2, "options": [{"id": "a", "total_price": 500}]},
        ]
        price_range = flights_agent._calculate_price_range(segments)
        assert price_range == "$500"

    def test_single_price_no_range(self, flights_agent):
        """When min equals max, no range shown."""
        segments = [
            {"id": 1, "options": [{"id": "a", "total_price": 500}]},
        ]
        price_range = flights_agent._calculate_price_range(segments)
        assert price_range == "$500"

    def test_no_selection_no_best_returns_none(self, flights_agent):
        """Total price returns None when no selection or best option."""
        segments = [
            {"id": 1, "options": [{"id": "a", "total_price": 500}]},
        ]
        total = flights_agent._calculate_total_price(segments)
        assert total is None

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_error(self, flights_agent):
        """Unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await flights_agent.execute_tool_async("unknown_tool", {})

    def test_legacy_execute_tool_still_works(self, flights_agent):
        """Legacy execute_tool for backward compatibility."""
        result = flights_agent.execute_tool(
            "search_flights", {"origin": "JFK", "destination": "AGP"}
        )
        assert result["status"] == "search_initiated"
