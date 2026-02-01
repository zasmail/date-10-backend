"""Pydantic schemas for activity and guide recommendations."""

from typing import List, Optional
from pydantic import BaseModel, Field


class LocalOperator(BaseModel):
    """A local tour operator or guide."""

    name: str = Field(..., description="Operator/guide name")
    destination: str = Field(..., description="Where they operate")
    activities: List[str] = Field(..., description="Activities they offer")
    specialty: str = Field(..., description="What they specialize in")
    price_range: str = Field("", description="Typical price range")
    contact: Optional[str] = Field(None, description="Contact info if available")
    notes: str = Field("", description="Additional notes")


class ActivityExpertise(BaseModel):
    """Detailed expertise for an adventure activity."""

    activity: str = Field(..., description="Activity name")
    skill_requirements: str = Field(..., description="Required skill level")
    gear_needed: str = Field(..., description="Essential gear")
    safety_considerations: List[str] = Field(default_factory=list)
    best_conditions: str = Field(..., description="Optimal conditions")
    permits_required: str = Field("", description="Any permits needed")


class ActivityRecommendation(BaseModel):
    """A recommended activity for a destination."""

    activity: str
    destination: str
    why_now: str = Field(..., description="Why this activity at this time")
    skill_level: str
    duration: str
    cost_estimate: str
    operator: Optional[LocalOperator] = None
    tips: List[str] = Field(default_factory=list)


class ActivityRecommendations(BaseModel):
    """Structured activity recommendations."""

    destination: str
    season: Optional[str] = None
    recommendations: List[ActivityRecommendation] = Field(..., min_length=1, max_length=5)
    summary: str


class OperatorKnowledgeEntry(BaseModel):
    """Entry in the operator knowledge base."""

    name: str
    destination: str
    activities: List[str]
    specialty: str
    price_range: str
    contact: Optional[str] = None
    website: Optional[str] = None
    notes: str = ""
    last_verified: Optional[str] = None


class OperatorKnowledgeBase(BaseModel):
    """Root schema for operator knowledge."""

    version: str
    last_updated: str
    operators: List[OperatorKnowledgeEntry]
