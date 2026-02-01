"""Pydantic schemas for destination knowledge base validation."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ActivitySeasonality(BaseModel):
    """Seasonality data for a specific activity at a destination."""

    season: List[int] = Field(..., description="Months (1-12) when activity is in season")
    reliability: Optional[str] = Field(None, description="Wind/conditions reliability percentage")
    conditions: str = Field(..., description="Description of typical conditions")
    skill_level: Optional[str] = Field(None, description="Recommended skill level")
    notes: str = Field("", description="Additional activity-specific notes")

    @field_validator('season')
    @classmethod
    def validate_months(cls, v: List[int]) -> List[int]:
        """Ensure all months are in valid range 1-12."""
        for month in v:
            if not 1 <= month <= 12:
                raise ValueError(f'Month must be between 1 and 12, got {month}')
        return v


class ClimateData(BaseModel):
    """Climate information for a destination."""

    best_months: List[int] = Field(..., description="Best months to visit (1-12)")
    avg_temp_c: Dict[str, int] = Field(..., description="Average temps by season (e.g., 'summer': 28)")
    rainy_months: List[int] = Field(default_factory=list, description="Rainy season months (1-12)")

    @field_validator('best_months', 'rainy_months')
    @classmethod
    def validate_climate_months(cls, v: List[int]) -> List[int]:
        """Ensure all months are in valid range 1-12."""
        for month in v:
            if not 1 <= month <= 12:
                raise ValueError(f'Month must be between 1 and 12, got {month}')
        return v


class LogisticsInfo(BaseModel):
    """Travel logistics information."""

    airports: List[str] = Field(..., description="Nearby airports (IATA codes)")
    from_airport: str = Field(..., description="Main arrival airport with transfer info")
    visa: str = Field(..., description="Visa requirements for US/EU citizens")


class AccommodationInfo(BaseModel):
    """Accommodation style and budget information."""

    style: str = Field(..., description="Typical accommodation style (boutique, surf camp, etc.)")
    budget_range: str = Field(..., description="Nightly price range (e.g., '$80-200/night')")
    areas: List[str] = Field(..., description="Recommended areas to stay")


class Destination(BaseModel):
    """A curated adventure travel destination."""

    name: str = Field(..., description="Destination name (e.g., 'Tarifa')")
    country: str = Field(..., description="Country name")
    region: Optional[str] = Field(None, description="Region/province if relevant")
    coordinates: Optional[List[float]] = Field(None, description="[lat, lng] coordinates")
    activities: Dict[str, ActivitySeasonality] = Field(..., description="Activities with seasonality")
    climate: ClimateData
    logistics: LogisticsInfo
    accommodation: AccommodationInfo
    vibe: str = Field(..., description="Overall destination vibe/character")
    why_go: str = Field(..., description="Top reasons to visit")
    why_skip: str = Field(..., description="Reasons this might not be right for someone")
    last_updated: Optional[str] = Field(None, description="Last update date (YYYY-MM)")


class DestinationKnowledgeBase(BaseModel):
    """Root schema for the destination knowledge base."""

    version: str = Field(..., description="Knowledge base version")
    last_updated: str = Field(..., description="Last update date")
    destinations: List[Destination] = Field(..., description="List of curated destinations")
