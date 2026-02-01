"""Pydantic schemas for accommodation recommendations."""

from typing import List, Optional
from pydantic import BaseModel, Field


class AccommodationOption(BaseModel):
    """A single accommodation recommendation."""

    name: str = Field(..., description="Property name")
    destination: str = Field(..., description="Destination name")
    area: str = Field(..., description="Neighborhood/area")
    style: str = Field(..., description="Accommodation style (boutique, surf camp, etc.)")
    price_range: str = Field(..., description="Nightly price range")
    highlights: List[str] = Field(default_factory=list, description="Key features")
    best_for: List[str] = Field(default_factory=list, description="Ideal guest types")
    booking_notes: str = Field("", description="Booking tips or caveats")
    why_recommended: str = Field("", description="Why this fits the user")


class AccommodationRecommendations(BaseModel):
    """Structured accommodation recommendations from Claude."""

    destination: str
    style_preference: Optional[str] = None
    budget_range: Optional[str] = None
    recommendations: List[AccommodationOption] = Field(..., min_length=1, max_length=5)
    summary: str = Field(..., description="Brief summary of options")


class AccommodationKnowledgeEntry(BaseModel):
    """A single entry in the accommodation knowledge base."""

    name: str
    destination: str
    area: str
    style: str
    price_range: str
    highlights: List[str]
    best_for: List[str]
    booking_url: Optional[str] = None
    last_verified: Optional[str] = None


class AccommodationKnowledgeBase(BaseModel):
    """Root schema for accommodation knowledge."""

    version: str
    last_updated: str
    accommodations: List[AccommodationKnowledgeEntry]
