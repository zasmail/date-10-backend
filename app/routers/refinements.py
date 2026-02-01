"""Itinerary refinement API endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from app.database import get_session, engine
from app.models import Itinerary
from app.services.refinement_service import refine_itinerary_streaming

router = APIRouter(prefix="/itineraries", tags=["refinements"])


class RefineRequest(BaseModel):
    """Request to refine an itinerary through natural language."""

    message: str  # User's refinement request (e.g., "swap day 3 and day 4")
    proposal_id: Optional[str] = None  # Which proposal to refine (uses selected if not specified)


@router.post("/{itinerary_id}/refine")
async def refine_itinerary(
    itinerary_id: str,
    request: RefineRequest,
    session: Session = Depends(get_session),
):
    """
    Refine an itinerary through natural language conversation.

    Streams SSE events:
    - text: Text response chunks
    - tool_use: When Claude uses a refinement tool
    - tool_result: Result of tool execution
    - error: If something goes wrong
    - done: Completion with updated proposal and usage stats

    The itinerary is automatically saved after refinement.
    """
    # Load the itinerary
    itinerary = session.get(Itinerary, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    # Parse proposals
    proposals = json.loads(itinerary.proposals_json)
    if not proposals:
        raise HTTPException(status_code=400, detail="Itinerary has no proposals")

    # Determine which proposal to refine
    proposal_id = request.proposal_id or itinerary.selected_proposal_id
    if not proposal_id:
        # Use first proposal if none selected
        proposal_id = proposals[0]["id"]

    # Find the proposal
    proposal = None
    proposal_index = None
    for i, p in enumerate(proposals):
        if p["id"] == proposal_id:
            proposal = p
            proposal_index = i
            break

    if proposal is None:
        raise HTTPException(status_code=400, detail=f"Proposal {proposal_id} not found")

    # Build messages for Claude (single turn for now)
    messages = [{"role": "user", "content": request.message}]

    async def event_generator():
        """Generate SSE events for streaming refinement."""
        updated_proposal = None
        text_response = ""

        try:
            async for event in refine_itinerary_streaming(proposal, messages):
                if event["type"] == "text":
                    text_response += event["content"]
                    yield {"event": "text", "data": json.dumps(event)}

                elif event["type"] == "tool_use":
                    yield {"event": "tool_use", "data": json.dumps(event)}

                elif event["type"] == "tool_result":
                    if event.get("success"):
                        updated_proposal = event["proposal"]
                    yield {"event": "tool_result", "data": json.dumps(event)}

                elif event["type"] == "done":
                    # Save the updated proposal to database
                    if updated_proposal or event.get("proposal"):
                        final_proposal = updated_proposal or event["proposal"]

                        # Update the proposal in the list
                        with Session(engine) as save_session:
                            itinerary_to_update = save_session.get(Itinerary, itinerary_id)
                            if itinerary_to_update:
                                current_proposals = json.loads(itinerary_to_update.proposals_json)
                                current_proposals[proposal_index] = final_proposal
                                itinerary_to_update.proposals_json = json.dumps(current_proposals)

                                # Update dates if they changed
                                if final_proposal.get("start_date"):
                                    # Check if start_date exists as attribute
                                    days = final_proposal.get("days", [])
                                    if days:
                                        itinerary_to_update.start_date = days[0].get("date", itinerary_to_update.start_date)
                                        itinerary_to_update.end_date = days[-1].get("date", itinerary_to_update.end_date)

                                save_session.add(itinerary_to_update)
                                save_session.commit()

                        event["itinerary_id"] = itinerary_id
                        event["proposal_id"] = proposal_id

                    yield {"event": "done", "data": json.dumps(event)}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(event_generator())
