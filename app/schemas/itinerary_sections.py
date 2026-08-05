"""Pydantic schemas for sectioned itinerary architecture.

This module defines discrete sections (Overview, Flights, Accommodations,
Activities, Logistics) that can be independently updated by specialized agents.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import re

from pydantic import BaseModel, Field, field_validator, model_validator


# Date format pattern for validation
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class OverviewSection(BaseModel):
    """Trip overview and high-level info."""

    destination: str = Field(..., description="Destination name")
    start_date: str = Field(..., description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Trip end date (YYYY-MM-DD)")
    num_travelers: int = Field(default=1, ge=1, description="Number of travelers")
    title: str = Field(..., description="Itinerary title/theme")
    summary: str = Field(..., description="2-3 sentence overview")
    highlights: List[str] = Field(default_factory=list, description="Top highlights")
    total_budget_estimate: str = Field(..., description="Total trip cost range")
    notes: str = Field(default="", description="Additional notes")

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format."""
        if not DATE_PATTERN.match(v):
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v

    @model_validator(mode="after")
    def validate_dates(self):
        """Ensure end_date is >= start_date."""
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError(
                    f"end_date ({self.end_date}) must be >= start_date ({self.start_date})"
                )
        return self


class FlightOption(BaseModel):
    """A single flight option with segments (legacy display format)."""

    id: str = Field(..., description="Unique flight option identifier")
    airline: str = Field(..., description="Primary airline")
    departure_airport: str = Field(..., description="Departure airport code")
    arrival_airport: str = Field(..., description="Arrival airport code")
    departure_time: str = Field(..., description="Departure datetime")
    arrival_time: str = Field(..., description="Arrival datetime")
    duration: str = Field(..., description="Total flight duration")
    price: str = Field(..., description="Price (e.g., '$650')")
    segments: List[Dict[str, Any]] = Field(
        default_factory=list, description="Flight segments for multi-leg trips"
    )
    booking_link: Optional[str] = Field(
        default=None, description="Direct booking URL"
    )


# ============================================================================
# Multi-Segment Flight Schema (new segment-based architecture)
# ============================================================================


class FlightLegDetail(BaseModel):
    """A single flight within a segment option (what you physically fly)."""

    departure_airport: str = Field(..., description="Departure IATA code")
    arrival_airport: str = Field(..., description="Arrival IATA code")
    departure_time: str = Field(..., description="ISO datetime")
    arrival_time: str = Field(..., description="ISO datetime")
    airline: str = Field(..., description="Marketing airline code")
    flight_number: str = Field(..., description="Flight number")
    duration_minutes: int = Field(..., ge=0)
    operating_airline: Optional[str] = Field(
        default=None, description="Codeshare operating airline"
    )


class FlightSegmentOption(BaseModel):
    """One bookable option for a journey segment."""

    id: str = Field(..., description="Unique option identifier")
    legs: List[FlightLegDetail] = Field(default_factory=list)
    total_price: float = Field(..., ge=0)
    price_per_person: float = Field(..., ge=0)
    currency: str = Field(default="USD")
    is_virtual_interlining: bool = Field(default=False)
    warnings: List[str] = Field(default_factory=list)
    booking_url: Optional[str] = Field(default=None)


class FlightSegment(BaseModel):
    """A journey segment (origin -> destination) with multiple options."""

    id: int = Field(..., ge=1, description="Segment number (1, 2, 3...)")
    origin: str = Field(..., description="Origin IATA code")
    destination: str = Field(..., description="Destination IATA code")
    date: str = Field(..., description="Departure date YYYY-MM-DD")
    cabin_class: str = Field(default="E", description="E/B/F cabin")
    options: List[FlightSegmentOption] = Field(default_factory=list)
    selected_option_id: Optional[str] = Field(
        default=None, description="User-selected option"
    )
    best_option_id: Optional[str] = Field(
        default=None, description="Auto-selected cheapest"
    )

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        if not DATE_PATTERN.match(v):
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v


class FlightsSection(BaseModel):
    """Flight options for the trip - supports both legacy and multi-segment."""

    # Legacy fields (backward compatibility)
    outbound_flights: List[FlightOption] = Field(
        default_factory=list, description="Outbound flight options (legacy)"
    )
    return_flights: List[FlightOption] = Field(
        default_factory=list, description="Return flight options (legacy)"
    )
    selected_outbound_id: Optional[str] = Field(
        default=None, description="Selected outbound flight ID (legacy)"
    )
    selected_return_id: Optional[str] = Field(
        default=None, description="Selected return flight ID (legacy)"
    )

    # New multi-segment fields
    segments: List[FlightSegment] = Field(
        default_factory=list, description="Journey segments with options"
    )
    searched_at: Optional[str] = Field(
        default=None, description="Last search timestamp (ISO)"
    )
    total_price: Optional[float] = Field(
        default=None, description="Sum of selected segment prices"
    )
    price_range: Optional[str] = Field(
        default=None, description="Overall price range (e.g., '$800-$1200')"
    )

    # Shared
    search_params: Optional[Dict[str, Any]] = Field(
        default=None, description="Parameters used for flight search"
    )

    def get_selected_total(self) -> Optional[float]:
        """Calculate total price from selected segment options."""
        if not self.segments:
            return None
        total = 0.0
        for seg in self.segments:
            if seg.selected_option_id:
                option = next(
                    (o for o in seg.options if o.id == seg.selected_option_id), None
                )
                if option:
                    total += option.total_price
        return total if total > 0 else None


class AccommodationNight(BaseModel):
    """Accommodation for a specific night."""

    date: str = Field(..., description="Night date (YYYY-MM-DD)")
    name: str = Field(..., description="Property name")
    area: str = Field(..., description="Neighborhood or area")
    style: str = Field(..., description="Accommodation type/style")
    price_range: str = Field(..., description="Nightly rate range")
    notes: str = Field(default="", description="Special considerations")
    booking_link: Optional[str] = Field(
        default=None, description="Direct booking URL"
    )

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format."""
        if not DATE_PATTERN.match(v):
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v


class AccommodationsSection(BaseModel):
    """All accommodations for the trip."""

    nights: List[AccommodationNight] = Field(
        default_factory=list, description="Accommodation for each night"
    )
    total_accommodation_cost: Optional[str] = Field(
        default=None, description="Estimated total accommodation cost"
    )


class ActivityItem(BaseModel):
    """A single activity within a day."""

    time: str = Field(..., description="Time of day (e.g., '09:00', 'morning')")
    name: str = Field(..., description="Activity name")
    description: str = Field(..., description="What this activity involves")
    duration: str = Field(..., description="How long (e.g., '2 hours')")
    location: Optional[str] = Field(
        default=None, description="Specific location if relevant"
    )
    cost_estimate: Optional[str] = Field(
        default=None, description="Price range (e.g., '$50-80')"
    )
    booking_required: bool = Field(
        default=False, description="Whether advance booking is needed"
    )
    operator: Optional[str] = Field(
        default=None, description="Local operator/guide name"
    )


class ActivityDay(BaseModel):
    """Activities for a single day."""

    day_number: int = Field(..., ge=1, description="Day number in itinerary")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    title: str = Field(..., description="Day title (e.g., 'Arrival & Orientation')")
    location: str = Field(..., description="Primary location for this day")
    activities: List[ActivityItem] = Field(
        default_factory=list, description="Activities for the day"
    )
    notes: str = Field(default="", description="Day-specific notes or tips")

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format."""
        if not DATE_PATTERN.match(v):
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v


class ActivitiesSection(BaseModel):
    """Day-by-day activities."""

    days: List[ActivityDay] = Field(
        default_factory=list, description="Activities organized by day"
    )
    total_activities_cost: Optional[str] = Field(
        default=None, description="Estimated total activities cost"
    )


class LogisticsSection(BaseModel):
    """Practical logistics and tips."""

    transportation_notes: List[str] = Field(
        default_factory=list, description="Ground transportation info"
    )
    packing_suggestions: List[str] = Field(
        default_factory=list, description="What to pack"
    )
    booking_requirements: List[str] = Field(
        default_factory=list, description="Things to book in advance"
    )
    visa_requirements: Optional[str] = Field(
        default=None, description="Visa/entry requirements"
    )
    health_notes: List[str] = Field(
        default_factory=list, description="Health/vaccination info"
    )
    caveats: List[str] = Field(
        default_factory=list, description="Things to consider/watch out for"
    )


class SectionedItinerary(BaseModel):
    """Complete itinerary split into specialized sections.

    This model enables independent updates to each section by specialized
    agents while maintaining a coherent overall itinerary structure.
    """

    id: str = Field(..., description="Unique itinerary identifier")
    overview: OverviewSection = Field(..., description="Trip overview")
    flights: FlightsSection = Field(
        default_factory=FlightsSection, description="Flight options"
    )
    accommodations: AccommodationsSection = Field(
        default_factory=AccommodationsSection, description="Accommodations"
    )
    activities: ActivitiesSection = Field(
        default_factory=ActivitiesSection, description="Day-by-day activities"
    )
    logistics: LogisticsSection = Field(
        default_factory=LogisticsSection, description="Logistics and tips"
    )
    version: int = Field(default=1, ge=1, description="Version number")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Last update timestamp (ISO format)")

    @model_validator(mode="after")
    def validate_activities_match_dates(self):
        """Validate that activity days align with the date range."""
        if not self.activities.days:
            # No activities yet - that's valid for initial creation
            return self

        # Calculate expected day count from overview
        start = datetime.strptime(self.overview.start_date, "%Y-%m-%d")
        end = datetime.strptime(self.overview.end_date, "%Y-%m-%d")
        expected_days = (end - start).days + 1

        # Check activity day count
        actual_days = len(self.activities.days)
        if actual_days > 0 and actual_days != expected_days:
            raise ValueError(
                f"Activity days count ({actual_days}) doesn't match "
                f"date range ({expected_days} days from {self.overview.start_date} "
                f"to {self.overview.end_date})"
            )

        return self


__all__ = [
    "OverviewSection",
    "FlightOption",
    "FlightLegDetail",
    "FlightSegmentOption",
    "FlightSegment",
    "FlightsSection",
    "AccommodationNight",
    "AccommodationsSection",
    "ActivityItem",
    "ActivityDay",
    "ActivitiesSection",
    "LogisticsSection",
    "SectionedItinerary",
]
