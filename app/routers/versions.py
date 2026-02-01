"""Version history API endpoints for itineraries."""

from typing import List, Optional
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from app.database import get_session
from app.models import Itinerary
from app.models.itinerary_version import ItineraryVersion
from app.services.version_service import (
    get_versions,
    get_version,
    rollback_to_version,
)

router = APIRouter(prefix="/itineraries", tags=["versions"])


class VersionSummary(BaseModel):
    """Summary of a version for list view."""

    id: str
    version_number: int
    destination: str
    start_date: str
    end_date: str
    change_description: str
    created_at: datetime


class VersionDetail(BaseModel):
    """Full version detail including proposals."""

    id: str
    itinerary_id: str
    version_number: int
    destination: str
    start_date: str
    end_date: str
    num_travelers: int
    proposals: List[dict]
    selected_proposal_id: Optional[str]
    change_description: str
    created_at: datetime


class RollbackResponse(BaseModel):
    """Response after rollback operation."""

    status: str
    message: str
    itinerary_id: str
    rolled_back_to_version: int


@router.get("/{itinerary_id}/versions", response_model=List[VersionSummary])
async def list_versions(
    itinerary_id: str,
    session: Session = Depends(get_session),
):
    """
    List all versions for an itinerary.

    Returns versions in reverse chronological order (newest first).
    """
    # Verify itinerary exists
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    versions = get_versions(session, itinerary_id)

    return [
        VersionSummary(
            id=v.id,
            version_number=v.version_number,
            destination=v.destination,
            start_date=v.start_date,
            end_date=v.end_date,
            change_description=v.change_description,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/{itinerary_id}/versions/{version_id}", response_model=VersionDetail)
async def get_version_detail(
    itinerary_id: str,
    version_id: str,
    session: Session = Depends(get_session),
):
    """
    Get full details of a specific version.

    Includes the complete proposals data for that version.
    """
    # Verify itinerary exists
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    version = get_version(session, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Verify version belongs to this itinerary
    if version.itinerary_id != itinerary_id:
        raise HTTPException(status_code=404, detail="Version not found for this itinerary")

    return VersionDetail(
        id=version.id,
        itinerary_id=version.itinerary_id,
        version_number=version.version_number,
        destination=version.destination,
        start_date=version.start_date,
        end_date=version.end_date,
        num_travelers=version.num_travelers,
        proposals=json.loads(version.proposals_json),
        selected_proposal_id=version.selected_proposal_id,
        change_description=version.change_description,
        created_at=version.created_at,
    )


@router.post("/{itinerary_id}/versions/{version_id}/rollback", response_model=RollbackResponse)
async def rollback_itinerary(
    itinerary_id: str,
    version_id: str,
    session: Session = Depends(get_session),
):
    """
    Roll back an itinerary to a previous version.

    This restores the itinerary state from the specified version.
    A new version is created to preserve the state before rollback.
    """
    # Verify itinerary exists
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    version = get_version(session, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Verify version belongs to this itinerary
    if version.itinerary_id != itinerary_id:
        raise HTTPException(status_code=404, detail="Version not found for this itinerary")

    # Perform the rollback
    rollback_to_version(session, itinerary, version)

    return RollbackResponse(
        status="ok",
        message=f"Itinerary rolled back to version {version.version_number}",
        itinerary_id=itinerary_id,
        rolled_back_to_version=version.version_number,
    )
