"""Accommodation API endpoints."""

import json

from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from pydantic import BaseModel

from app.database import get_session
from app.models import UserPreferences
from app.schemas.preferences import PreferencesData
from app.schemas.accommodation import AccommodationRecommendations, AccommodationOption
from app.knowledge.accommodation_knowledge import (
    get_accommodations_for_destination,
    load_accommodation_knowledge,
)
from app.services.accommodation_service import recommend_accommodations

router = APIRouter(prefix="/accommodations", tags=["accommodations"])


class AccommodationSearchRequest(BaseModel):
    """Request for accommodation recommendations."""

    destination: str
    message: str = "Recommend accommodations for me"


@router.get("/destinations")
async def list_accommodation_destinations():
    """List destinations with accommodation data."""
    kb = load_accommodation_knowledge()
    destinations = sorted(set(acc.destination for acc in kb.accommodations))
    return {"destinations": destinations, "total": len(destinations)}


@router.get("/{destination}")
async def get_destination_accommodations(destination: str):
    """Get all accommodations for a destination."""
    accommodations = get_accommodations_for_destination(destination)
    return {
        "destination": destination,
        "accommodations": [acc.model_dump() for acc in accommodations],
        "count": len(accommodations),
    }


@router.post("/recommend", response_model=AccommodationRecommendations)
async def get_recommendations(
    request: AccommodationSearchRequest,
    session: Session = Depends(get_session),
):
    """Get AI-powered accommodation recommendations."""
    # Get user preferences
    user_prefs = session.exec(
        select(UserPreferences).where(UserPreferences.user_id == "default")
    ).first()

    if user_prefs and user_prefs.preferences_json:
        preferences = PreferencesData(**json.loads(user_prefs.preferences_json))
    else:
        preferences = PreferencesData()

    messages = [{"role": "user", "content": request.message}]

    result = await recommend_accommodations(
        messages=messages,
        preferences=preferences,
        destination=request.destination,
    )

    if result.get("error"):
        # Return a simple response on error
        return AccommodationRecommendations(
            destination=request.destination,
            recommendations=[
                AccommodationOption(
                    name="See available options",
                    destination=request.destination,
                    area="Various",
                    style="Various",
                    price_range="Various",
                    why_recommended="Use GET /accommodations/{destination} for full list",
                )
            ],
            summary="Error getting AI recommendations. Try the destination endpoint instead.",
        )

    if result.get("recommendations"):
        return result["recommendations"]

    # Fallback to knowledge base
    kb_accommodations = get_accommodations_for_destination(request.destination)
    options = [
        AccommodationOption(
            name=acc.name,
            destination=acc.destination,
            area=acc.area,
            style=acc.style,
            price_range=acc.price_range,
            highlights=acc.highlights,
            best_for=acc.best_for,
            why_recommended=f"Matches {acc.style.lower()} style",
        )
        for acc in kb_accommodations[:5]
    ]

    return AccommodationRecommendations(
        destination=request.destination,
        recommendations=options,
        summary=f"Found {len(options)} options in {request.destination}",
    )
