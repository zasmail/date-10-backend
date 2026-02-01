from typing import List, Optional

from pydantic import BaseModel, Field


class TravelerProfile(BaseModel):
    """Individual traveler profile with name and optional description."""

    name: str
    description: Optional[str] = None


class DestinationPreferences(BaseModel):
    """Destination-related preferences including bucket list and exclusions."""

    bucket_list: List[str] = Field(default_factory=list)
    visited: List[str] = Field(default_factory=list)
    no_go: List[str] = Field(default_factory=list)


class ActivityPreferences(BaseModel):
    """Activity preferences including types and intensity level."""

    preferred: List[str] = Field(default_factory=list)
    intensity_level: str = "high"


class AccommodationPreferences(BaseModel):
    """Accommodation preferences including style, budget, and requirements."""

    style: str = "boutique"
    max_nightly_rate: int = 500
    requirements: List[str] = Field(default_factory=list)


class BudgetPreferences(BaseModel):
    """Budget preferences including currency and spending limits."""

    currency: str = "USD"
    daily_budget: Optional[int] = None
    flight_budget_per_person: Optional[int] = None


class PreferencesData(BaseModel):
    """Complete user preferences document for travel planning."""

    travelers: List[TravelerProfile] = Field(default_factory=list)
    destinations: DestinationPreferences = Field(default_factory=DestinationPreferences)
    activities: ActivityPreferences = Field(default_factory=ActivityPreferences)
    accommodation: AccommodationPreferences = Field(
        default_factory=AccommodationPreferences
    )
    budget: BudgetPreferences = Field(default_factory=BudgetPreferences)
    notes: Optional[str] = None
