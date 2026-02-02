"""Claude chat service with tool support for itineraries and flights."""

import json
import uuid
from typing import Any, AsyncGenerator, Dict, List

from anthropic import AsyncAnthropic

from app.prompts.travel_assistant import build_system_prompt
from app.schemas.preferences import PreferencesData
from app.schemas.itinerary import ItineraryData
from app.services.flight_service import search_flights, get_iata_code
from app.schemas.flight import FlightSearchRequest, FlightSegmentRequest

client = AsyncAnthropic()  # Uses ANTHROPIC_API_KEY env var


# Tool definitions
GENERATE_ITINERARY_TOOL = {
    "name": "generate_itinerary",
    "description": """Generate a structured day-by-day travel itinerary. Call this tool when the user asks for:
- An itinerary or trip plan
- A day-by-day schedule or breakdown
- Help planning specific dates at a destination
- A detailed trip proposal

Generate ONE complete proposal with:
- A clear title and 2-3 sentence summary
- Complete day-by-day breakdown with activities, times, and logistics
- Budget estimate, highlights, and caveats

If the user wants alternative options, they can request another itinerary with a different theme (e.g., "Adventure Focus", "Relaxed Pace", "Cultural Immersion").""",
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
                "default": 2,
            },
            "proposal": {
                "type": "object",
                "description": "Single itinerary proposal",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Proposal theme (e.g., 'Adventure Focus', 'Balanced Exploration')",
                    },
                    "summary": {
                        "type": "string",
                        "description": "2-3 sentence overview of this itinerary",
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
        "required": ["destination", "start_date", "end_date", "proposal"],
    },
}

SEARCH_FLIGHTS_TOOL = {
    "name": "search_flights",
    "description": """Search for real flight options. Call this tool when:
- User asks about flights or airfare
- User wants to know flight costs for a trip
- You've generated an itinerary and want to provide flight options
- User asks how to get to a destination

Returns actual flight prices and options from airlines.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Departure city or airport code (e.g., 'NYC', 'JFK', 'New York')",
            },
            "destination": {
                "type": "string",
                "description": "Arrival city or airport code",
            },
            "departure_date": {
                "type": "string",
                "description": "Departure date (YYYY-MM-DD)",
            },
            "return_date": {
                "type": "string",
                "description": "Return date (YYYY-MM-DD) - omit for one-way",
            },
            "num_travelers": {
                "type": "integer",
                "description": "Number of adult travelers",
                "default": 2,
            },
            "cabin_class": {
                "type": "string",
                "enum": ["E", "B", "F"],
                "description": "E=Economy, B=Business, F=First",
                "default": "E",
            },
        },
        "required": ["origin", "destination", "departure_date"],
    },
}

TOOLS = [GENERATE_ITINERARY_TOOL, SEARCH_FLIGHTS_TOOL]


async def execute_flight_search(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Execute flight search tool and return results."""
    origin = tool_input.get("origin", "")
    destination = tool_input.get("destination", "")
    departure_date = tool_input.get("departure_date", "")
    return_date = tool_input.get("return_date")
    num_travelers = tool_input.get("num_travelers", 2)
    cabin_class = tool_input.get("cabin_class", "E")

    # Convert city names to IATA codes
    origin_iata = get_iata_code(origin.lower()) or origin.upper()[:3]
    dest_iata = get_iata_code(destination.lower()) or destination.upper()[:3]

    segments = [
        FlightSegmentRequest(
            id=1,
            departure_date=departure_date,
            cabin_class=cabin_class,
            from_iata=origin_iata,
            to_iata=dest_iata,
            from_type="C",
            to_type="C",
        )
    ]

    # Add return segment if return_date provided
    if return_date:
        segments.append(
            FlightSegmentRequest(
                id=2,
                departure_date=return_date,
                cabin_class=cabin_class,
                from_iata=dest_iata,
                to_iata=origin_iata,
                from_type="C",
                to_type="C",
            )
        )

    travellers = ["ADT"] * num_travelers

    request = FlightSearchRequest(
        segments=segments,
        travellers=travellers,
        currency="USD",
        virtual_interlining=True,
    )

    result = await search_flights(request)
    # Use mode='json' to serialize datetime objects as ISO strings
    return result.model_dump(mode='json')


async def stream_response(
    messages: List[Dict[str, str]], preferences: PreferencesData
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream Claude response with tool support."""

    system_prompt = build_system_prompt(preferences)

    async with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        system=system_prompt,
        messages=messages,
        tools=TOOLS,
        tool_choice={"type": "auto"},
    ) as stream:
        tool_uses = {}  # Track tool uses by ID
        current_tool_id = None
        current_tool_name = None

        async for event in stream:
            print(f"[DEBUG claude_service] Event: {event.type}")
            if event.type == "content_block_start":
                if hasattr(event.content_block, "type"):
                    if event.content_block.type == "text":
                        pass  # Text block starting
                    elif event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        current_tool_name = event.content_block.name
                        tool_uses[current_tool_id] = {
                            "name": current_tool_name,
                            "input_json": "",
                        }
                        yield {
                            "type": "tool_start",
                            "tool_name": current_tool_name,
                            "tool_id": current_tool_id,
                        }

            elif event.type == "content_block_delta":
                if hasattr(event.delta, "text"):
                    yield {"type": "text", "content": event.delta.text}
                elif hasattr(event.delta, "partial_json"):
                    if current_tool_id and current_tool_id in tool_uses:
                        tool_uses[current_tool_id]["input_json"] += event.delta.partial_json
                        print(f"[DEBUG claude_service] Accumulating JSON for {current_tool_name}, len={len(tool_uses[current_tool_id]['input_json'])}")

            elif event.type == "content_block_stop":
                print(f"[DEBUG claude_service] content_block_stop, current_tool_id={current_tool_id}")
                if current_tool_id and current_tool_id in tool_uses:
                    tool_data = tool_uses[current_tool_id]
                    print(f"[DEBUG claude_service] Tool {tool_data['name']} input_json length: {len(tool_data['input_json'])}")
                    try:
                        tool_input = json.loads(tool_data["input_json"])
                        print(f"[DEBUG claude_service] Parsed tool_input keys: {list(tool_input.keys())}")

                        if tool_data["name"] == "generate_itinerary":
                            print(f"[DEBUG claude_service] Processing generate_itinerary")
                            # Convert single proposal to proposals array for compatibility
                            proposal = tool_input.get("proposal")
                            if proposal and "id" not in proposal:
                                proposal["id"] = str(uuid.uuid4())

                            # Wrap single proposal in array for existing data structure
                            tool_input["proposals"] = [proposal] if proposal else []
                            del tool_input["proposal"]  # Remove the singular key

                            itinerary_data = ItineraryData(**tool_input)
                            print(f"[DEBUG claude_service] ItineraryData validated! Destination: {itinerary_data.destination}")
                            yield {
                                "type": "itinerary",
                                "tool_id": current_tool_id,
                                "data": itinerary_data.model_dump(),
                            }

                        elif tool_data["name"] == "search_flights":
                            # Execute the flight search
                            yield {
                                "type": "flight_search_start",
                                "tool_id": current_tool_id,
                                "query": tool_input,
                            }
                            flight_results = await execute_flight_search(tool_input)
                            yield {
                                "type": "flights",
                                "tool_id": current_tool_id,
                                "data": flight_results,
                            }

                    except Exception as e:
                        print(f"[DEBUG claude_service] Tool error: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        yield {
                            "type": "tool_error",
                            "tool_id": current_tool_id,
                            "error": str(e),
                        }

                    current_tool_id = None
                    current_tool_name = None

        final_message = await stream.get_final_message()
        yield {
            "type": "done",
            "usage": {
                "input_tokens": final_message.usage.input_tokens,
                "output_tokens": final_message.usage.output_tokens,
            },
        }
