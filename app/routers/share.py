"""Share and export router for itineraries."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response, JSONResponse
from sqlmodel import Session, select
from pydantic import BaseModel

from app.database import get_session
from app.models.itinerary import Itinerary
from app.models.shared_itinerary import SharedItinerary
from app.services.export_service import itinerary_to_markdown, itinerary_to_json


router = APIRouter(tags=["share"])


class ShareLinkCreate(BaseModel):
    """Request body for creating a share link."""
    title: Optional[str] = None


class ShareLinkResponse(BaseModel):
    """Response after creating a share link."""
    token: str
    share_url: str
    title: Optional[str] = None
    created_at: str


class SharedItineraryResponse(BaseModel):
    """Public response for shared itinerary."""
    destination: str
    start_date: str
    end_date: str
    num_travelers: int
    title: Optional[str] = None
    proposals: list
    view_count: int


@router.get("/itineraries/{itinerary_id}/export/markdown")
async def export_markdown(
    itinerary_id: str,
    proposal_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Export itinerary as downloadable Markdown file.

    Query params:
    - proposal_id: Export specific proposal (optional)
    """
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    markdown_content = itinerary_to_markdown(itinerary, proposal_id)

    # Generate filename
    filename = f"{itinerary.destination.lower().replace(' ', '-')}-itinerary.md"

    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/itineraries/{itinerary_id}/export/json")
async def export_json(
    itinerary_id: str,
    proposal_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Export itinerary as downloadable JSON file.

    Query params:
    - proposal_id: Export specific proposal (optional)
    """
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    json_data = itinerary_to_json(itinerary, proposal_id)

    # Generate filename
    filename = f"{itinerary.destination.lower().replace(' ', '-')}-itinerary.json"

    return Response(
        content=json.dumps(json_data, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/itineraries/{itinerary_id}/share", response_model=ShareLinkResponse)
async def create_share_link(
    itinerary_id: str,
    body: ShareLinkCreate = ShareLinkCreate(),
    session: Session = Depends(get_session)
):
    """
    Create a shareable read-only link for an itinerary.

    The share link allows anyone with the token to view the itinerary
    without authentication.
    """
    # Verify itinerary exists
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    # Check for existing active share link
    statement = select(SharedItinerary).where(
        SharedItinerary.itinerary_id == itinerary_id,
        SharedItinerary.is_active == True
    )
    existing = session.exec(statement).first()

    if existing:
        # Return existing share link
        return ShareLinkResponse(
            token=existing.share_token,
            share_url=f"/share/{existing.share_token}",
            title=existing.title,
            created_at=existing.created_at.isoformat()
        )

    # Create new share link
    title = body.title or f"{itinerary.destination} Itinerary"
    shared = SharedItinerary(
        itinerary_id=itinerary_id,
        title=title
    )
    session.add(shared)
    session.commit()
    session.refresh(shared)

    return ShareLinkResponse(
        token=shared.share_token,
        share_url=f"/share/{shared.share_token}",
        title=shared.title,
        created_at=shared.created_at.isoformat()
    )


@router.get("/share/{token}", response_model=SharedItineraryResponse)
async def get_shared_itinerary(
    token: str,
    session: Session = Depends(get_session)
):
    """
    Get shared itinerary by token (public endpoint - no auth required).

    This increments the view count each time it's accessed.
    """
    # Find share link
    statement = select(SharedItinerary).where(
        SharedItinerary.share_token == token,
        SharedItinerary.is_active == True
    )
    shared = session.exec(statement).first()

    if not shared:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    # Get the itinerary
    itinerary = session.get(Itinerary, shared.itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary no longer exists")

    # Increment view count
    shared.view_count += 1
    session.add(shared)
    session.commit()

    # Return public data
    return SharedItineraryResponse(
        destination=itinerary.destination,
        start_date=itinerary.start_date,
        end_date=itinerary.end_date,
        num_travelers=itinerary.num_travelers,
        title=shared.title,
        proposals=itinerary_to_json(itinerary)["proposals"],
        view_count=shared.view_count
    )


@router.delete("/itineraries/{itinerary_id}/share")
async def revoke_share_link(
    itinerary_id: str,
    session: Session = Depends(get_session)
):
    """
    Revoke (deactivate) the share link for an itinerary.
    """
    statement = select(SharedItinerary).where(
        SharedItinerary.itinerary_id == itinerary_id,
        SharedItinerary.is_active == True
    )
    shared = session.exec(statement).first()

    if not shared:
        raise HTTPException(status_code=404, detail="No active share link found")

    shared.is_active = False
    session.add(shared)
    session.commit()

    return {"message": "Share link revoked"}
