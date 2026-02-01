"""Accommodation recommendation service with Claude tool."""

from typing import Any, Dict, List

from anthropic import AsyncAnthropic

from app.prompts.travel_assistant import build_system_prompt
from app.schemas.preferences import PreferencesData
from app.schemas.accommodation import AccommodationRecommendations, AccommodationOption
from app.knowledge.accommodation_knowledge import format_accommodations_for_prompt

client = AsyncAnthropic()

RECOMMEND_ACCOMMODATIONS_TOOL = {
    "name": "recommend_accommodations",
    "description": """Recommend accommodations for a destination. Call this when the user asks for hotel, accommodation, or stay recommendations.

Use the accommodation_knowledge provided in the system prompt to make informed recommendations.
Always explain WHY each recommendation fits the user's preferences.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "destination": {"type": "string", "description": "Destination for accommodations"},
            "style_preference": {
                "type": "string",
                "description": "Preferred style (boutique, surf camp, eco-lodge, etc.)",
            },
            "budget_range": {"type": "string", "description": "Budget range if specified"},
            "recommendations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "destination": {"type": "string"},
                        "area": {"type": "string"},
                        "style": {"type": "string"},
                        "price_range": {"type": "string"},
                        "highlights": {"type": "array", "items": {"type": "string"}},
                        "best_for": {"type": "array", "items": {"type": "string"}},
                        "booking_notes": {"type": "string"},
                        "why_recommended": {"type": "string"},
                    },
                    "required": [
                        "name",
                        "destination",
                        "area",
                        "style",
                        "price_range",
                        "why_recommended",
                    ],
                },
            },
            "summary": {
                "type": "string",
                "description": "Brief summary of options and recommendation",
            },
        },
        "required": ["destination", "recommendations", "summary"],
    },
}


async def recommend_accommodations(
    messages: List[Dict[str, str]],
    preferences: PreferencesData,
    destination: str,
) -> Dict[str, Any]:
    """
    Get accommodation recommendations using Claude's tool use.

    Returns dict with:
    - recommendations: AccommodationRecommendations if successful
    - text_response: Claude's explanation
    - error: Error message if failed
    """
    # Build system prompt with accommodation knowledge
    system_prompt = build_system_prompt(preferences)

    # Add accommodation knowledge block
    accommodation_knowledge = format_accommodations_for_prompt(destination)
    system_prompt.append(
        {
            "type": "text",
            "text": accommodation_knowledge,
            "cache_control": {"type": "ephemeral"},
        }
    )

    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
        tools=[RECOMMEND_ACCOMMODATIONS_TOOL],
        tool_choice={"type": "auto"},
    )

    result = {
        "recommendations": None,
        "text_response": "",
        "tool_used": False,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }

    for block in response.content:
        if block.type == "text":
            result["text_response"] += block.text
        elif block.type == "tool_use":
            if block.name == "recommend_accommodations":
                result["tool_used"] = True
                try:
                    tool_input = block.input

                    # Parse recommendations
                    options = []
                    for rec in tool_input.get("recommendations", []):
                        options.append(
                            AccommodationOption(
                                name=rec.get("name", ""),
                                destination=rec.get("destination", ""),
                                area=rec.get("area", ""),
                                style=rec.get("style", ""),
                                price_range=rec.get("price_range", ""),
                                highlights=rec.get("highlights", []),
                                best_for=rec.get("best_for", []),
                                booking_notes=rec.get("booking_notes", ""),
                                why_recommended=rec.get("why_recommended", ""),
                            )
                        )

                    result["recommendations"] = AccommodationRecommendations(
                        destination=tool_input.get("destination", destination),
                        style_preference=tool_input.get("style_preference"),
                        budget_range=tool_input.get("budget_range"),
                        recommendations=options,
                        summary=tool_input.get("summary", ""),
                    )
                except Exception as e:
                    result["error"] = f"Failed to parse recommendations: {str(e)}"

    return result
