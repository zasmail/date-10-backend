"""Flight search API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models import Itinerary
from app.schemas.flight import (
    FlightSearchRequest,
    FlightSearchResponse,
    FlightSegmentRequest,
)
from app.services.flight_service import search_flights, build_segments_from_itinerary

router = APIRouter(prefix="/flights", tags=["flights"])


@router.post("/search", response_model=FlightSearchResponse)
async def search_flights_endpoint(
    request: FlightSearchRequest,
):
    """
    Search for flights with custom segments.

    This is a direct search endpoint - for most use cases,
    use /itineraries/{id}/flights instead.
    """
    if not request.segments:
        raise HTTPException(status_code=400, detail="At least one segment required")

    return await search_flights(request)


@router.post("/itinerary/{itinerary_id}", response_model=FlightSearchResponse)
async def search_flights_for_itinerary(
    itinerary_id: str,
    origin: str,
    num_travelers: int = 1,
    cabin_class: str = "E",
    currency: str = "USD",
    session: Session = Depends(get_session),
):
    """
    Search for flights based on an itinerary's destinations and dates.

    Automatically builds multi-city segments from the itinerary.
    """
    # Get the itinerary
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    # Get the selected proposal or first proposal
    proposals = json.loads(itinerary.proposals_json)
    if not proposals:
        raise HTTPException(status_code=400, detail="Itinerary has no proposals")

    selected_id = itinerary.selected_proposal_id
    proposal = None
    for p in proposals:
        if selected_id and p["id"] == selected_id:
            proposal = p
            break
    if not proposal:
        proposal = proposals[0]

    # Extract destinations and dates from the proposal days
    destinations = []
    dates = []

    # First segment: origin to first day's location
    if proposal.get("days"):
        first_day = proposal["days"][0]
        destinations.append(first_day.get("location", itinerary.destination))
        dates.append(first_day.get("date", itinerary.start_date))

        # If there are location changes within the trip, add those as segments
        current_location = first_day.get("location")
        for day in proposal["days"][1:]:
            day_location = day.get("location")
            if day_location and day_location != current_location:
                destinations.append(day_location)
                dates.append(day.get("date"))
                current_location = day_location

    if not destinations:
        destinations = [itinerary.destination]
        dates = [itinerary.start_date]

    # Build segments
    segments = build_segments_from_itinerary(
        origin=origin,
        destinations=destinations,
        dates=dates,
        cabin_class=cabin_class,
    )

    # Add return segment if end_date is different from last segment date
    if itinerary.end_date and itinerary.end_date != dates[-1]:
        segments.append(
            FlightSegmentRequest(
                id=len(segments) + 1,
                departure_date=itinerary.end_date,
                cabin_class=cabin_class,
                from_iata=segments[-1].to_iata if segments else "",
                to_iata=segments[0].from_iata if segments else "",
                from_type="C",
                to_type="C",
            )
        )

    # Build traveller list
    travellers = ["ADT"] * num_travelers

    request = FlightSearchRequest(
        segments=segments,
        travellers=travellers,
        currency=currency,
        virtual_interlining=True,
    )

    return await search_flights(request)


@router.get("/iata/{destination}")
async def get_iata_code_endpoint(destination: str):
    """Look up IATA code for a destination name."""
    from app.services.flight_service import get_iata_code

    code = get_iata_code(destination)
    if not code:
        return {
            "destination": destination,
            "iata_code": None,
            "message": "Destination not found in mapping. Try using the IATA code directly.",
        }
    return {"destination": destination, "iata_code": code}
