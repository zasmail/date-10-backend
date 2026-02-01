"""Tests for flight service."""

from app.services.flight_service import (
    get_iata_code,
    build_segments_from_itinerary,
)


class TestGetIataCode:
    """Tests for IATA code lookup."""

    def test_known_destination(self):
        """Lookup known destination."""
        assert get_iata_code("Tarifa") == "AGP"
        assert get_iata_code("Cape Town") == "CPT"
        assert get_iata_code("Bali") == "DPS"

    def test_case_insensitive(self):
        """Lookup is case insensitive."""
        assert get_iata_code("tarifa") == "AGP"
        assert get_iata_code("TARIFA") == "AGP"
        assert get_iata_code("TaRiFa") == "AGP"

    def test_unknown_destination(self):
        """Unknown destination returns None."""
        assert get_iata_code("Unknown City") is None
        assert get_iata_code("Mars") is None

    def test_with_whitespace(self):
        """Handles whitespace."""
        assert get_iata_code("  Tarifa  ") == "AGP"


class TestBuildSegmentsFromItinerary:
    """Tests for segment building."""

    def test_single_destination(self):
        """Simple round trip."""
        segments = build_segments_from_itinerary(
            origin="New York",
            destinations=["Tarifa"],
            dates=["2026-05-15"],
        )
        assert len(segments) == 1
        assert segments[0].from_iata == "JFK"
        assert segments[0].to_iata == "AGP"
        assert segments[0].departure_date == "2026-05-15"

    def test_multi_city(self):
        """Multi-city itinerary."""
        segments = build_segments_from_itinerary(
            origin="New York",
            destinations=["Tarifa", "Cape Town"],
            dates=["2026-05-15", "2026-05-22"],
        )
        assert len(segments) == 2
        assert segments[0].from_iata == "JFK"
        assert segments[0].to_iata == "AGP"
        assert segments[1].from_iata == "AGP"
        assert segments[1].to_iata == "CPT"

    def test_segment_ids_sequential(self):
        """Segment IDs are sequential."""
        segments = build_segments_from_itinerary(
            origin="Los Angeles",
            destinations=["Tarifa", "Cape Town", "Bali"],
            dates=["2026-05-15", "2026-05-22", "2026-05-29"],
        )
        assert [s.id for s in segments] == [1, 2, 3]

    def test_custom_cabin_class(self):
        """Custom cabin class."""
        segments = build_segments_from_itinerary(
            origin="New York",
            destinations=["Tarifa"],
            dates=["2026-05-15"],
            cabin_class="B",
        )
        assert segments[0].cabin_class == "B"

    def test_unknown_origin_uses_as_code(self):
        """Unknown origin is used as-is (uppercase)."""
        segments = build_segments_from_itinerary(
            origin="xyz",
            destinations=["Tarifa"],
            dates=["2026-05-15"],
        )
        assert segments[0].from_iata == "XYZ"
