"""Itinerary API endpoints."""

from typing import List, Optional
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from app.database import get_session, engine
from app.models import Itinerary, Conversation, Message, UserPreferences
from app.schemas.preferences import PreferencesData
from app.services.itinerary_service import generate_itinerary_streaming

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


class GenerateItineraryRequest(BaseModel):
    """Request to generate an itinerary."""

    message: str  # User's request (e.g., "Create a 5-day itinerary for Tarifa in May")
    conversation_id: Optional[str] = None


class ItineraryResponse(BaseModel):
    """Itinerary response model."""

    id: str
    destination: str
    start_date: str
    end_date: str
    num_travelers: int
    proposals: List[dict]
    selected_proposal_id: Optional[str]
    created_at: datetime


class SelectProposalRequest(BaseModel):
    """Request to select a proposal."""

    proposal_id: str


@router.post("/generate")
async def generate_itinerary_endpoint(
    request: GenerateItineraryRequest,
    session: Session = Depends(get_session),
):
    """Generate an itinerary via streaming SSE."""
    # Get user preferences
    user_prefs = session.exec(
        select(UserPreferences).where(UserPreferences.user_id == "default")
    ).first()

    if user_prefs and user_prefs.preferences_json:
        preferences = PreferencesData(**json.loads(user_prefs.preferences_json))
    else:
        preferences = PreferencesData()

    # Build messages for Claude
    messages = []

    # If conversation_id provided, include conversation history
    if request.conversation_id:
        conversation = session.get(Conversation, request.conversation_id)
        if conversation:
            db_messages = session.exec(
                select(Message)
                .where(Message.conversation_id == request.conversation_id)
                .order_by(Message.created_at)
            ).all()
            for msg in db_messages:
                messages.append({"role": msg.role, "content": msg.content})

    # Add the current request
    messages.append({"role": "user", "content": request.message})

    async def event_generator():
        """Generate SSE events for streaming response."""
        itinerary_data = None
        text_response = ""

        async for event in generate_itinerary_streaming(messages, preferences):
            if event["type"] == "text":
                text_response += event["content"]
                yield {"event": "text", "data": json.dumps(event)}

            elif event["type"] == "tool_start":
                yield {"event": "tool_start", "data": json.dumps(event)}

            elif event["type"] == "itinerary":
                itinerary_data = event["data"]
                yield {"event": "itinerary", "data": json.dumps(event)}

            elif event["type"] == "error":
                yield {"event": "error", "data": json.dumps(event)}

            elif event["type"] == "done":
                # Save the itinerary to database if we got one
                if itinerary_data:
                    # Use a new session for the save operation
                    with Session(engine) as save_session:
                        itinerary = Itinerary(
                            conversation_id=request.conversation_id,
                            destination=itinerary_data["destination"],
                            start_date=itinerary_data["start_date"],
                            end_date=itinerary_data["end_date"],
                            num_travelers=itinerary_data.get("num_travelers", 1),
                            proposals_json=json.dumps(itinerary_data["proposals"]),
                            selected_proposal_id=itinerary_data.get("selected_proposal_id"),
                        )
                        save_session.add(itinerary)
                        save_session.commit()
                        save_session.refresh(itinerary)

                        event["itinerary_id"] = itinerary.id

                yield {"event": "done", "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@router.get("", response_model=List[ItineraryResponse])
async def list_itineraries(
    session: Session = Depends(get_session),
    limit: int = 20,
):
    """List all itineraries for the current user."""
    itineraries = session.exec(
        select(Itinerary)
        .where(Itinerary.user_id == "default")
        .order_by(Itinerary.created_at.desc())
        .limit(limit)
    ).all()

    return [
        ItineraryResponse(
            id=it.id,
            destination=it.destination,
            start_date=it.start_date,
            end_date=it.end_date,
            num_travelers=it.num_travelers,
            proposals=json.loads(it.proposals_json),
            selected_proposal_id=it.selected_proposal_id,
            created_at=it.created_at,
        )
        for it in itineraries
    ]


@router.get("/{itinerary_id}", response_model=ItineraryResponse)
async def get_itinerary(
    itinerary_id: str,
    session: Session = Depends(get_session),
):
    """Get a specific itinerary by ID."""
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    return ItineraryResponse(
        id=itinerary.id,
        destination=itinerary.destination,
        start_date=itinerary.start_date,
        end_date=itinerary.end_date,
        num_travelers=itinerary.num_travelers,
        proposals=json.loads(itinerary.proposals_json),
        selected_proposal_id=itinerary.selected_proposal_id,
        created_at=itinerary.created_at,
    )


@router.post("/{itinerary_id}/select")
async def select_proposal(
    itinerary_id: str,
    request: SelectProposalRequest,
    session: Session = Depends(get_session),
):
    """Select a proposal as the active itinerary."""
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    # Verify proposal_id exists
    proposals = json.loads(itinerary.proposals_json)
    proposal_ids = [p["id"] for p in proposals]
    if request.proposal_id not in proposal_ids:
        raise HTTPException(status_code=400, detail="Invalid proposal ID")

    itinerary.selected_proposal_id = request.proposal_id
    itinerary.updated_at = datetime.utcnow()
    session.add(itinerary)
    session.commit()

    return {"status": "ok", "selected_proposal_id": request.proposal_id}


@router.delete("/{itinerary_id}")
async def delete_itinerary(
    itinerary_id: str,
    session: Session = Depends(get_session),
):
    """Delete an itinerary."""
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    session.delete(itinerary)
    session.commit()

    return {"status": "deleted"}
