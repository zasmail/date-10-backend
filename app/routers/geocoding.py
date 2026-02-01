"""Geocoding API endpoints for map visualization."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.knowledge.destination_knowledge import load_knowledge_base

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


class GeocodedLocation(BaseModel):
    """Response model for geocoded location."""

    name: str
    lat: float
    lng: float
    source: str  # 'knowledge_base' or 'geocode_api'
    country: Optional[str] = None
    region: Optional[str] = None


@router.get("/{location}", response_model=GeocodedLocation)
async def geocode_location(location: str) -> GeocodedLocation:
    """Get coordinates for a location.

    First checks the destination knowledge base for known destinations.
    Returns coordinates if found.

    Args:
        location: Location name to geocode (e.g., 'Tarifa', 'Cape Town')

    Returns:
        GeocodedLocation with name, lat, lng, and source

    Raises:
        HTTPException: 404 if location not found
    """
    # Normalize the search term
    location_lower = location.lower().strip()

    # Search in knowledge base first
    kb = load_knowledge_base()

    for dest in kb.destinations:
        if dest.name.lower() == location_lower:
            if dest.coordinates:
                return GeocodedLocation(
                    name=dest.name,
                    lat=dest.coordinates[0],
                    lng=dest.coordinates[1],
                    source="knowledge_base",
                    country=dest.country,
                    region=dest.region,
                )
            break

    # If not found in knowledge base, return 404
    # In a production system, we would fall back to a geocoding API like Mapbox or Google
    raise HTTPException(
        status_code=404,
        detail=f"Location '{location}' not found in knowledge base. "
        "For unknown locations, a geocoding API integration would be needed.",
    )


@router.get("")
async def list_known_locations() -> list[GeocodedLocation]:
    """List all known locations from the destination knowledge base.

    Returns:
        List of GeocodedLocation objects for all destinations with coordinates
    """
    kb = load_knowledge_base()
    locations = []

    for dest in kb.destinations:
        if dest.coordinates:
            locations.append(
                GeocodedLocation(
                    name=dest.name,
                    lat=dest.coordinates[0],
                    lng=dest.coordinates[1],
                    source="knowledge_base",
                    country=dest.country,
                    region=dest.region,
                )
            )

    return locations
