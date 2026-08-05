"""Agent chat endpoint for testing agents in isolation."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import json

from app.agents.flights_agent import FlightsAgent
from app.agents.base_agent import SectionHandoff

router = APIRouter(prefix="/agent-chat", tags=["agent-chat"])


class AgentChatMessage(BaseModel):
    """A chat message for the agent."""
    role: str  # "user" or "assistant"
    content: str


class AgentChatRequest(BaseModel):
    """Request to chat with an agent."""
    agent_type: str  # "flights", "accommodations", etc.
    messages: List[AgentChatMessage]
    context: Dict[str, Any] = {}  # Optional context (itinerary info, etc.)


async def stream_agent_response(agent, messages, context):
    """Stream agent responses as SSE events."""

    # Build handoff with context
    handoff = SectionHandoff(
        section_type=agent.SECTION_TYPE,
        user_request=messages[-1].content if messages else "",
        current_state=context.get("current_state", {}),
        related_sections=context.get("related_sections", {}),
        constraints=context.get("constraints", {}),
    )

    # Convert messages to Claude format
    claude_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]

    try:
        async for event in agent.process(handoff, claude_messages):
            # Stream each event as SSE
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as e:
        error_event = {
            "type": "error",
            "message": str(e)
        }
        yield f"data: {json.dumps(error_event)}\n\n"


@router.post("/flights")
async def chat_with_flights_agent(request: AgentChatRequest):
    """Chat with the flights agent."""
    agent = FlightsAgent()

    return StreamingResponse(
        stream_agent_response(agent, request.messages, request.context),
        media_type="text/event-stream",
    )
