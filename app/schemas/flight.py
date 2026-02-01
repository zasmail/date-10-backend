"""Pydantic schemas for flight search and results."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FlightSegmentRequest(BaseModel):
    """A segment in a flight search request (one leg of the journey)."""

    id: int
    departure_date: str = Field(..., description="Date in YYYY-MM-DD format")
    cabin_class: str = Field("E", description="E=economy, B=business, F=first")
    from_iata: str = Field(..., description="Origin airport/city IATA code")
    to_iata: str = Field(..., description="Destination airport/city IATA code")
    from_type: str = Field("C", description="C=city, A=airport")
    to_type: str = Field("C", description="C=city, A=airport")


class FlightSearchRequest(BaseModel):
    """Request body for Trip Ninja API."""

    segments: List[FlightSegmentRequest]
    travellers: List[str] = Field(
        default=["ADT"], description="Passenger types: ADT, CHD, INF"
    )
    currency: str = Field("USD", description="ISO currency code")
    virtual_interlining: bool = Field(
        True, description="Enable multi-ticket optimization"
    )


class FlightLeg(BaseModel):
    """A single flight within a segment."""

    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    airline: str
    flight_number: str
    duration_minutes: int
    operating_airline: Optional[str] = None


class FlightSegmentResult(BaseModel):
    """Result for one segment of the journey."""

    segment_id: int
    flights: List[FlightLeg]


class FlightOption(BaseModel):
    """A complete flight option (may include multiple segments)."""

    id: str
    total_price: float
    currency: str
    price_per_person: float
    segments: List[FlightSegmentResult]
    is_virtual_interlining: bool = False
    warnings: List[str] = Field(default_factory=list)
    booking_url: Optional[str] = None


class FlightSearchResponse(BaseModel):
    """Response from flight search."""

    search_id: str
    searched_at: datetime
    origin: str
    destination: str
    options: List[FlightOption]
    cheapest_price: Optional[float] = None
    price_range: Optional[str] = None


class ItineraryFlightSearch(BaseModel):
    """Request to search flights for an itinerary."""

    itinerary_id: str
    num_travelers: int = Field(1, ge=1)
    cabin_class: str = Field("E", description="E=economy, B=business, F=first")
    currency: str = Field("USD")
