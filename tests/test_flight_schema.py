"""Tests for flight Pydantic schemas."""

from datetime import datetime

from app.schemas.flight import (
    FlightSegmentRequest,
    FlightSearchRequest,
    FlightLeg,
    FlightSegmentResult,
    FlightOption,
    FlightSearchResponse,
)


class TestFlightSegmentRequest:
    """Tests for FlightSegmentRequest schema."""

    def test_valid_segment(self):
        """Basic segment with required fields."""
        segment = FlightSegmentRequest(
            id=1,
            departure_date="2026-05-15",
            from_iata="JFK",
            to_iata="AGP",
        )
        assert segment.cabin_class == "E"  # Default
        assert segment.from_type == "C"  # Default

    def test_segment_with_all_fields(self):
        """Segment with all fields specified."""
        segment = FlightSegmentRequest(
            id=1,
            departure_date="2026-05-15",
            cabin_class="B",
            from_iata="JFK",
            to_iata="AGP",
            from_type="A",
            to_type="A",
        )
        assert segment.cabin_class == "B"
        assert segment.from_type == "A"


class TestFlightSearchRequest:
    """Tests for FlightSearchRequest schema."""

    def test_valid_request(self):
        """Request with segments."""
        request = FlightSearchRequest(
            segments=[
                FlightSegmentRequest(
                    id=1, departure_date="2026-05-15", from_iata="JFK", to_iata="AGP"
                )
            ]
        )
        assert len(request.segments) == 1
        assert request.travellers == ["ADT"]  # Default
        assert request.virtual_interlining is True  # Default

    def test_multi_city_request(self):
        """Multi-city request."""
        request = FlightSearchRequest(
            segments=[
                FlightSegmentRequest(
                    id=1, departure_date="2026-05-15", from_iata="JFK", to_iata="AGP"
                ),
                FlightSegmentRequest(
                    id=2, departure_date="2026-05-22", from_iata="AGP", to_iata="CPT"
                ),
                FlightSegmentRequest(
                    id=3, departure_date="2026-05-29", from_iata="CPT", to_iata="JFK"
                ),
            ],
            travellers=["ADT", "ADT"],
            currency="EUR",
        )
        assert len(request.segments) == 3
        assert len(request.travellers) == 2


class TestFlightLeg:
    """Tests for FlightLeg schema."""

    def test_valid_leg(self):
        """Basic flight leg."""
        leg = FlightLeg(
            departure_airport="JFK",
            arrival_airport="AGP",
            departure_time="2026-05-15T20:00:00",
            arrival_time="2026-05-16T08:00:00",
            airline="IB",
            flight_number="IB3456",
            duration_minutes=540,
        )
        assert leg.airline == "IB"
        assert leg.duration_minutes == 540


class TestFlightOption:
    """Tests for FlightOption schema."""

    def test_valid_option(self):
        """Complete flight option."""
        option = FlightOption(
            id="opt-1",
            total_price=1250.00,
            currency="USD",
            price_per_person=1250.00,
            segments=[
                FlightSegmentResult(
                    segment_id=1,
                    flights=[
                        FlightLeg(
                            departure_airport="JFK",
                            arrival_airport="AGP",
                            departure_time="2026-05-15T20:00:00",
                            arrival_time="2026-05-16T08:00:00",
                            airline="IB",
                            flight_number="IB3456",
                            duration_minutes=540,
                        )
                    ],
                )
            ],
        )
        assert option.total_price == 1250.00
        assert len(option.segments) == 1

    def test_option_with_warnings(self):
        """Option with virtual interlining warnings."""
        option = FlightOption(
            id="opt-1",
            total_price=1100.00,
            currency="USD",
            price_per_person=1100.00,
            segments=[],
            is_virtual_interlining=True,
            warnings=[
                "Split ticket - bags may not transfer",
                "Allow 3+ hours for connection",
            ],
        )
        assert option.is_virtual_interlining is True
        assert len(option.warnings) == 2


class TestFlightSearchResponse:
    """Tests for FlightSearchResponse schema."""

    def test_valid_response(self):
        """Complete search response."""
        response = FlightSearchResponse(
            search_id="search-123",
            searched_at=datetime.utcnow(),
            origin="JFK",
            destination="AGP",
            options=[],
            cheapest_price=1100.00,
            price_range="$1100-$1500",
        )
        assert response.origin == "JFK"
        assert response.cheapest_price == 1100.00

    def test_empty_response(self):
        """Response with no options."""
        response = FlightSearchResponse(
            search_id="search-123",
            searched_at=datetime.utcnow(),
            origin="JFK",
            destination="XYZ",
            options=[],
        )
        assert len(response.options) == 0
        assert response.cheapest_price is None
