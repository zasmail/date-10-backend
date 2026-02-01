import json
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from app.database import get_session
from app.models.conversation import Conversation, Message
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
    return [{"role": m.role, "content": m.content} for m in messages]


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

        # Send conversation_id first so frontend knows it
        yield {
            "data": json.dumps(
                {"type": "conversation_id", "conversation_id": conversation_id}
            )
        }

        async for chunk in stream_response(messages, preferences):
            if chunk["type"] == "text":
                full_response += chunk["content"]
                yield {"data": json.dumps(chunk)}
            elif chunk["type"] == "done":
                input_tokens = chunk["usage"]["input_tokens"]
                output_tokens = chunk["usage"]["output_tokens"]
                yield {"data": json.dumps(chunk)}

        # Save assistant message after streaming completes
        # Need a new session since the original may be closed
        from app.database import engine

        with Session(engine) as save_session:
            assistant_message = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            save_session.add(assistant_message)

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
    """Get a conversation with all messages."""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
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
    }
