"""Itinerary generation service using Claude tool use."""

from typing import Any, AsyncGenerator, Dict, List
import uuid
import json

from anthropic import AsyncAnthropic

from app.prompts.travel_assistant import build_system_prompt
from app.schemas.preferences import PreferencesData
from app.schemas.itinerary import ItineraryData

client = AsyncAnthropic()

# Tool definition for structured itinerary generation
GENERATE_ITINERARY_TOOL = {
    "name": "generate_itinerary",
    "description": """Generate a structured day-by-day travel itinerary. Call this tool when the user asks for an itinerary, trip plan, schedule, or day-by-day breakdown for specific dates and destination.

IMPORTANT: Always generate 2-3 distinct proposals with different themes (e.g., "Adventure Focus", "Relaxed Pace", "Cultural Immersion").

Each proposal should have:
- A clear title and 2-3 sentence summary
- Complete day-by-day breakdown with activities, times, and logistics
- Budget estimate, highlights, and caveats""",
    "input_schema": {
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "description": "Primary destination (city/region)",
            },
            "start_date": {
                "type": "string",
                "description": "Trip start date (YYYY-MM-DD)",
            },
            "end_date": {
                "type": "string",
                "description": "Trip end date (YYYY-MM-DD)",
            },
            "num_travelers": {
                "type": "integer",
                "description": "Number of travelers",
                "default": 1,
            },
            "proposals": {
                "type": "array",
                "description": "2-3 alternative itinerary proposals",
                "minItems": 2,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Proposal theme (e.g., 'Adventure Focus')",
                        },
                        "summary": {
                            "type": "string",
                            "description": "2-3 sentence overview of this option",
                        },
                        "days": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "day_number": {"type": "integer"},
                                    "date": {"type": "string"},
                                    "title": {"type": "string"},
                                    "location": {"type": "string"},
                                    "activities": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "time": {"type": "string"},
                                                "name": {"type": "string"},
                                                "description": {"type": "string"},
                                                "duration": {"type": "string"},
                                                "location": {"type": "string"},
                                                "cost_estimate": {"type": "string"},
                                                "booking_required": {
                                                    "type": "boolean",
                                                    "default": False,
                                                },
                                            },
                                            "required": [
                                                "time",
                                                "name",
                                                "description",
                                                "duration",
                                            ],
                                        },
                                    },
                                    "accommodation": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "area": {"type": "string"},
                                            "style": {"type": "string"},
                                            "price_range": {"type": "string"},
                                            "notes": {"type": "string"},
                                        },
                                        "required": ["name", "area", "style", "price_range"],
                                    },
                                    "notes": {"type": "string"},
                                },
                                "required": [
                                    "day_number",
                                    "date",
                                    "title",
                                    "location",
                                    "activities",
                                ],
                            },
                        },
                        "total_budget_estimate": {
                            "type": "string",
                            "description": "Total trip cost range (e.g., '$1500-2000')",
                        },
                        "highlights": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Top 3-5 highlights of this option",
                        },
                        "caveats": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Things to consider with this option",
                        },
                    },
                    "required": [
                        "title",
                        "summary",
                        "days",
                        "total_budget_estimate",
                        "highlights",
                        "caveats",
                    ],
                },
            },
        },
        "required": ["destination", "start_date", "end_date", "proposals"],
    },
}


async def generate_itinerary(
    messages: List[Dict[str, str]],
    preferences: PreferencesData,
) -> Dict[str, Any]:
    """
    Generate an itinerary using Claude's tool use.

    Returns dict with:
    - itinerary: ItineraryData if successful
    - text_response: Claude's text explanation
    - error: Error message if failed
    """
    system_prompt = build_system_prompt(preferences)

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,  # Itineraries need more tokens
        system=system_prompt,
        messages=messages,
        tools=[GENERATE_ITINERARY_TOOL],
        tool_choice={"type": "auto"},  # Let Claude decide when to use the tool
    )

    result = {
        "itinerary": None,
        "text_response": "",
        "tool_used": False,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }

    # Process response content blocks
    for block in response.content:
        if block.type == "text":
            result["text_response"] += block.text
        elif block.type == "tool_use":
            if block.name == "generate_itinerary":
                result["tool_used"] = True
                try:
                    # Parse and validate the tool input
                    tool_input = block.input

                    # Add UUIDs to proposals if not present
                    for proposal in tool_input.get("proposals", []):
                        if "id" not in proposal:
                            proposal["id"] = str(uuid.uuid4())

                    itinerary_data = ItineraryData(**tool_input)
                    result["itinerary"] = itinerary_data
                except Exception as e:
                    result["error"] = f"Failed to parse itinerary: {str(e)}"

    return result


async def generate_itinerary_streaming(
    messages: List[Dict[str, str]],
    preferences: PreferencesData,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generate itinerary with streaming for progress updates.

    Yields events:
    - {"type": "text", "content": "..."} - Text chunks
    - {"type": "tool_start", "name": "generate_itinerary"} - Tool invocation started
    - {"type": "itinerary", "data": {...}} - Complete itinerary data
    - {"type": "done", "usage": {...}} - Completion
    """
    system_prompt = build_system_prompt(preferences)

    async with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        system=system_prompt,
        messages=messages,
        tools=[GENERATE_ITINERARY_TOOL],
        tool_choice={"type": "auto"},
    ) as stream:
        tool_inputs: Dict[str, str] = {}
        current_tool_id = None

        async for event in stream:
            if event.type == "content_block_start":
                if hasattr(event.content_block, "type"):
                    if event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        tool_inputs[current_tool_id] = ""
                        yield {"type": "tool_start", "name": event.content_block.name}

            elif event.type == "content_block_delta":
                if hasattr(event.delta, "text"):
                    yield {"type": "text", "content": event.delta.text}
                elif hasattr(event.delta, "partial_json"):
                    if current_tool_id:
                        tool_inputs[current_tool_id] += event.delta.partial_json

            elif event.type == "content_block_stop":
                if current_tool_id and current_tool_id in tool_inputs:
                    try:
                        tool_input = json.loads(tool_inputs[current_tool_id])
                        # Add UUIDs to proposals
                        for proposal in tool_input.get("proposals", []):
                            if "id" not in proposal:
                                proposal["id"] = str(uuid.uuid4())

                        itinerary_data = ItineraryData(**tool_input)
                        yield {"type": "itinerary", "data": itinerary_data.model_dump()}
                    except Exception as e:
                        yield {"type": "error", "message": f"Failed to parse itinerary: {str(e)}"}

                    current_tool_id = None

        final_message = await stream.get_final_message()
        yield {
            "type": "done",
            "usage": {
                "input_tokens": final_message.usage.input_tokens,
                "output_tokens": final_message.usage.output_tokens,
            },
        }
