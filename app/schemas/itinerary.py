"""Pydantic schemas for itinerary validation."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Activity(BaseModel):
    """A single activity in an itinerary day."""

    time: str = Field(..., description="Time of day (e.g., '09:00', 'morning', 'afternoon')")
    name: str = Field(..., description="Activity name")
    description: str = Field(..., description="What this activity involves")
    duration: str = Field(..., description="How long (e.g., '2 hours', 'half day')")
    location: Optional[str] = Field(None, description="Specific location if relevant")
    cost_estimate: Optional[str] = Field(None, description="Price range (e.g., '$50-80')")
    booking_required: bool = Field(False, description="Whether advance booking is needed")


class Accommodation(BaseModel):
    """Accommodation for a night."""

    name: str = Field(..., description="Property name or type")
    area: str = Field(..., description="Neighborhood or area")
    style: str = Field(..., description="Type (boutique hotel, surf camp, etc.)")
    price_range: str = Field(..., description="Nightly rate range")
    notes: str = Field("", description="Special considerations")


class ItineraryDay(BaseModel):
    """A single day in the itinerary."""

    day_number: int = Field(..., ge=1)
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    title: str = Field(..., description="Day title (e.g., 'Arrival & Orientation')")
    location: str = Field(..., description="Primary location for this day")
    activities: List[Activity] = Field(default_factory=list)
    accommodation: Optional[Accommodation] = None
    notes: str = Field("", description="Day-specific notes or tips")


class ItineraryProposal(BaseModel):
    """A single itinerary proposal with day-by-day details."""

    id: str = Field(..., description="Unique proposal identifier")
    title: str = Field(..., description="Proposal theme (e.g., 'Adventure Focus')")
    summary: str = Field(..., description="2-3 sentence overview")
    days: List[ItineraryDay]
    total_budget_estimate: str = Field(..., description="Total trip cost range")
    highlights: List[str] = Field(default_factory=list, description="Top 3-5 highlights")
    caveats: List[str] = Field(default_factory=list, description="Things to consider")


class ItineraryData(BaseModel):
    """Complete itinerary with one or more proposals."""

    destination: str
    start_date: str
    end_date: str
    num_travelers: int = Field(1, ge=1)
    proposals: List[ItineraryProposal] = Field(..., min_length=1, max_length=3)
    selected_proposal_id: Optional[str] = None
