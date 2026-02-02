import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from app.database import get_session, engine
from app.models.conversation import Conversation, Message
from app.models.itinerary import Itinerary
from app.models.user_preferences import UserPreferences
from app.schemas.chat import ChatRequest
from app.schemas.preferences import PreferencesData
from app.services.claude_service import stream_response

router = APIRouter(prefix="/chat", tags=["chat"])


def get_preferences(session: Session) -> PreferencesData:
    """Get user preferences or return defaults."""
    prefs = session.exec(select(UserPreferences)).first()
    if prefs:
        return prefs.get_preferences()
    return PreferencesData()


def get_conversation_messages(session: Session, conversation_id: str) -> List[Dict]:
    """Get messages formatted for Claude API."""
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    ).all()
    # Filter out messages with empty content (Claude API rejects these)
    return [
        {"role": m.role, "content": m.content}
        for m in messages
        if m.content and m.content.strip()
    ]


@router.post("/stream")
async def chat_stream(
    request: ChatRequest, session: Session = Depends(get_session)
):
    """Stream chat response from Claude via SSE."""

    # Get or create conversation
    if request.conversation_id:
        conversation = session.get(Conversation, request.conversation_id)
        if not conversation:
            conversation = Conversation(id=request.conversation_id)
            session.add(conversation)
    else:
        conversation = Conversation()
        session.add(conversation)

    session.commit()
    session.refresh(conversation)

    # Save user message
    user_message = Message(
        conversation_id=conversation.id, role="user", content=request.message
    )
    session.add(user_message)
    session.commit()

    # Get conversation history and preferences
    messages = get_conversation_messages(session, conversation.id)
    preferences = get_preferences(session)

    # Capture values needed in generator (session may be closed)
    conversation_id = conversation.id
    user_message_content = request.message
    is_first_exchange = len(messages) == 1

    async def generate():
        full_response = ""
        input_tokens = 0
        output_tokens = 0
        generated_itineraries = []  # Track itineraries to save

        # Send conversation_id first so frontend knows it
        yield {
            "data": json.dumps(
                {"type": "conversation_id", "conversation_id": conversation_id}
            )
        }

        async for chunk in stream_response(messages, preferences):
            print(f"[DEBUG] Received chunk type: {chunk['type']}")  # Debug log
            if chunk["type"] == "text":
                full_response += chunk["content"]
                yield {"data": json.dumps(chunk)}
            elif chunk["type"] == "tool_start":
                print(f"[DEBUG] Tool start: {chunk.get('tool_name')}")  # Debug log
                yield {"data": json.dumps(chunk)}
            elif chunk["type"] == "flight_search_start":
                yield {"data": json.dumps(chunk)}
            elif chunk["type"] == "itinerary":
                # Track the itinerary for saving
                print(f"[DEBUG] Itinerary received! Destination: {chunk['data'].get('destination')}")  # Debug log
                generated_itineraries.append(chunk["data"])
                yield {"data": json.dumps(chunk)}
            elif chunk["type"] == "flights":
                # Ensure datetime objects are serialized as ISO strings
                try:
                    yield {"data": json.dumps(chunk, default=str)}
                except Exception as e:
                    print(f"[DEBUG] Error serializing flights: {e}")
                    yield {"data": json.dumps({"type": "tool_error", "error": str(e)})}
            elif chunk["type"] == "tool_error":
                print(f"[DEBUG] Tool error: {chunk.get('error')}")  # Debug log
                yield {"data": json.dumps(chunk)}
            elif chunk["type"] == "done":
                input_tokens = chunk["usage"]["input_tokens"]
                output_tokens = chunk["usage"]["output_tokens"]
                print(f"[DEBUG] Done. Itineraries collected: {len(generated_itineraries)}")  # Debug log
                yield {"data": json.dumps(chunk)}

        # Save assistant message and itineraries after streaming completes
        with Session(engine) as save_session:
            # Only save assistant message if it has content
            if full_response and full_response.strip():
                assistant_message = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_response,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                save_session.add(assistant_message)

            # Save any generated itineraries
            print(f"[DEBUG] Saving {len(generated_itineraries)} itineraries to DB")  # Debug log
            for itinerary_data in generated_itineraries:
                print(f"[DEBUG] Saving itinerary: {itinerary_data.get('destination')}")  # Debug log
                itinerary = Itinerary(
                    conversation_id=conversation_id,
                    destination=itinerary_data.get("destination", ""),
                    start_date=itinerary_data.get("start_date", ""),
                    end_date=itinerary_data.get("end_date", ""),
                    num_travelers=itinerary_data.get("num_travelers", 2),
                    proposals_json=json.dumps(itinerary_data.get("proposals", [])),
                )
                save_session.add(itinerary)

            # Update conversation title if first exchange
            conv = save_session.get(Conversation, conversation_id)
            if conv and not conv.title and is_first_exchange:
                # Use first ~50 chars of user message as title
                conv.title = (
                    user_message_content[:50]
                    + ("..." if len(user_message_content) > 50 else "")
                )

            if conv:
                conv.updated_at = datetime.utcnow()

            save_session.commit()

    return EventSourceResponse(generate())


@router.get("/conversations")
async def list_conversations(session: Session = Depends(get_session)):
    """List all conversations."""
    conversations = session.exec(
        select(Conversation).order_by(Conversation.updated_at.desc())
    ).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str, session: Session = Depends(get_session)
):
    """Get a conversation with all messages and itineraries."""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    ).all()

    # Get itineraries for this conversation
    itineraries = session.exec(
        select(Itinerary)
        .where(Itinerary.conversation_id == conversation_id)
        .order_by(Itinerary.created_at)
    ).all()

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "itineraries": [
            {
                "id": it.id,
                "destination": it.destination,
                "start_date": it.start_date,
                "end_date": it.end_date,
                "num_travelers": it.num_travelers,
                "proposals": json.loads(it.proposals_json),
                "selected_proposal_id": it.selected_proposal_id,
                "created_at": it.created_at.isoformat(),
            }
            for it in itineraries
        ],
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, session: Session = Depends(get_session)
):
    """Delete a conversation and all its messages."""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete messages
    messages = session.exec(
        select(Message).where(Message.conversation_id == conversation_id)
    ).all()
    for m in messages:
        session.delete(m)

    # Delete itineraries
    itineraries = session.exec(
        select(Itinerary).where(Itinerary.conversation_id == conversation_id)
    ).all()
    for it in itineraries:
        session.delete(it)

    # Delete conversation
    session.delete(conversation)
    session.commit()

    return {"status": "deleted"}
