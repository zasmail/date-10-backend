"""Itinerary refinement service using Claude tool use for natural language edits."""

import json
import copy
from typing import Any, AsyncGenerator, Dict, List, Optional
from datetime import datetime, timedelta

from anthropic import AsyncAnthropic

from app.schemas.itinerary import (
    ItineraryProposal,
    ItineraryDay,
    Activity,
    Accommodation,
)

client = AsyncAnthropic()

# ============================================================================
# Tool Definitions for Itinerary Refinement
# ============================================================================

REFINEMENT_TOOLS = [
    {
        "name": "swap_days",
        "description": """Swap two days in the itinerary. Use when the user wants to reorder days,
such as 'swap day 3 and day 4' or 'move day 2 to day 5'.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "day_a": {
                    "type": "integer",
                    "description": "First day number to swap (1-indexed)",
                },
                "day_b": {
                    "type": "integer",
                    "description": "Second day number to swap (1-indexed)",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why this swap makes sense",
                },
            },
            "required": ["day_a", "day_b"],
        },
    },
    {
        "name": "add_day",
        "description": """Add a new day to the itinerary. Use when the user wants to insert a rest day,
extend the trip, or add a day for a specific activity like 'add a rest day after the trek'.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "after_day": {
                    "type": "integer",
                    "description": "Insert the new day after this day number (0 to insert at start)",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the new day (e.g., 'Rest & Recovery')",
                },
                "location": {
                    "type": "string",
                    "description": "Location for this day",
                },
                "activities": {
                    "type": "array",
                    "description": "Activities for the new day",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "duration": {"type": "string"},
                            "location": {"type": "string"},
                            "cost_estimate": {"type": "string"},
                        },
                        "required": ["time", "name", "description", "duration"],
                    },
                },
                "accommodation": {
                    "type": "object",
                    "description": "Accommodation for this night (optional - uses previous day's if not specified)",
                    "properties": {
                        "name": {"type": "string"},
                        "area": {"type": "string"},
                        "style": {"type": "string"},
                        "price_range": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                },
                "notes": {
                    "type": "string",
                    "description": "Any notes for this day",
                },
            },
            "required": ["after_day", "title", "location", "activities"],
        },
    },
    {
        "name": "remove_day",
        "description": """Remove a day from the itinerary. Use when the user wants to shorten the trip
or remove a specific day.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "day_number": {
                    "type": "integer",
                    "description": "Day number to remove (1-indexed)",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of what's being removed",
                },
            },
            "required": ["day_number"],
        },
    },
    {
        "name": "update_activity",
        "description": """Update, replace, or remove an activity on a specific day. Use when the user
wants to change timing, swap activities, or modify details.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "day_number": {
                    "type": "integer",
                    "description": "Day number containing the activity (1-indexed)",
                },
                "activity_index": {
                    "type": "integer",
                    "description": "Index of activity to update (0-indexed)",
                },
                "action": {
                    "type": "string",
                    "enum": ["update", "replace", "remove"],
                    "description": "What to do with the activity",
                },
                "new_activity": {
                    "type": "object",
                    "description": "New or updated activity data (not needed for 'remove')",
                    "properties": {
                        "time": {"type": "string"},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "duration": {"type": "string"},
                        "location": {"type": "string"},
                        "cost_estimate": {"type": "string"},
                        "booking_required": {"type": "boolean"},
                    },
                },
            },
            "required": ["day_number", "activity_index", "action"],
        },
    },
    {
        "name": "update_accommodation",
        "description": """Update accommodation for a specific day. Use when the user wants to
find a cheaper hotel, upgrade, or change where they're staying.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "day_number": {
                    "type": "integer",
                    "description": "Day number to update accommodation for (1-indexed)",
                },
                "accommodation": {
                    "type": "object",
                    "description": "New accommodation details",
                    "properties": {
                        "name": {"type": "string"},
                        "area": {"type": "string"},
                        "style": {"type": "string"},
                        "price_range": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": ["name", "area", "style", "price_range"],
                },
                "apply_to_consecutive": {
                    "type": "boolean",
                    "description": "Apply to consecutive days with same accommodation",
                    "default": False,
                },
            },
            "required": ["day_number", "accommodation"],
        },
    },
]


# ============================================================================
# Tool Execution Functions
# ============================================================================


def swap_days(proposal: Dict[str, Any], day_a: int, day_b: int, reason: str = "") -> Dict[str, Any]:
    """
    Swap two days in the itinerary.

    Args:
        proposal: The proposal dict to modify
        day_a: First day number (1-indexed)
        day_b: Second day number (1-indexed)
        reason: Optional explanation

    Returns:
        Modified proposal dict
    """
    result = copy.deepcopy(proposal)
    days = result.get("days", [])

    if not days:
        raise ValueError("Proposal has no days")

    # Convert to 0-indexed
    idx_a = day_a - 1
    idx_b = day_b - 1

    if idx_a < 0 or idx_a >= len(days):
        raise ValueError(f"Day {day_a} is out of range (1-{len(days)})")
    if idx_b < 0 or idx_b >= len(days):
        raise ValueError(f"Day {day_b} is out of range (1-{len(days)})")

    # Swap the days
    days[idx_a], days[idx_b] = days[idx_b], days[idx_a]

    # Update day numbers and dates
    _renumber_days(days, result.get("start_date"))

    return result


def add_day(
    proposal: Dict[str, Any],
    after_day: int,
    title: str,
    location: str,
    activities: List[Dict[str, Any]],
    accommodation: Optional[Dict[str, Any]] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Add a new day to the itinerary.

    Args:
        proposal: The proposal dict to modify
        after_day: Insert after this day (0 for start)
        title: Day title
        location: Day location
        activities: List of activity dicts
        accommodation: Optional accommodation dict
        notes: Optional notes

    Returns:
        Modified proposal dict
    """
    result = copy.deepcopy(proposal)
    days = result.get("days", [])

    if after_day < 0 or after_day > len(days):
        raise ValueError(f"after_day {after_day} is out of range (0-{len(days)})")

    # Create the new day
    new_day = {
        "day_number": after_day + 1,  # Will be renumbered
        "date": "",  # Will be recalculated
        "title": title,
        "location": location,
        "activities": activities,
        "notes": notes,
    }

    # Handle accommodation - use previous day's if not specified
    if accommodation:
        new_day["accommodation"] = accommodation
    elif after_day > 0 and days[after_day - 1].get("accommodation"):
        new_day["accommodation"] = copy.deepcopy(days[after_day - 1]["accommodation"])

    # Insert the new day
    days.insert(after_day, new_day)
    result["days"] = days

    # Renumber all days and recalculate dates
    _renumber_days(days, result.get("start_date"))

    # Update end_date
    if days and days[-1].get("date"):
        result["end_date"] = days[-1]["date"]

    return result


def remove_day(proposal: Dict[str, Any], day_number: int, reason: str = "") -> Dict[str, Any]:
    """
    Remove a day from the itinerary.

    Args:
        proposal: The proposal dict to modify
        day_number: Day to remove (1-indexed)
        reason: Optional explanation

    Returns:
        Modified proposal dict
    """
    result = copy.deepcopy(proposal)
    days = result.get("days", [])

    if not days:
        raise ValueError("Proposal has no days")

    idx = day_number - 1
    if idx < 0 or idx >= len(days):
        raise ValueError(f"Day {day_number} is out of range (1-{len(days)})")

    if len(days) <= 1:
        raise ValueError("Cannot remove the only day in the itinerary")

    # Remove the day
    days.pop(idx)

    # Renumber remaining days
    _renumber_days(days, result.get("start_date"))

    # Update end_date
    if days and days[-1].get("date"):
        result["end_date"] = days[-1]["date"]

    return result


def update_activity(
    proposal: Dict[str, Any],
    day_number: int,
    activity_index: int,
    action: str,
    new_activity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update, replace, or remove an activity.

    Args:
        proposal: The proposal dict to modify
        day_number: Day containing the activity (1-indexed)
        activity_index: Index of activity (0-indexed)
        action: "update", "replace", or "remove"
        new_activity: New activity data (for update/replace)

    Returns:
        Modified proposal dict
    """
    result = copy.deepcopy(proposal)
    days = result.get("days", [])

    idx = day_number - 1
    if idx < 0 or idx >= len(days):
        raise ValueError(f"Day {day_number} is out of range (1-{len(days)})")

    activities = days[idx].get("activities", [])

    if activity_index < 0 or activity_index >= len(activities):
        raise ValueError(f"Activity index {activity_index} is out of range (0-{len(activities) - 1})")

    if action == "remove":
        activities.pop(activity_index)
    elif action == "replace":
        if not new_activity:
            raise ValueError("new_activity required for replace action")
        activities[activity_index] = new_activity
    elif action == "update":
        if not new_activity:
            raise ValueError("new_activity required for update action")
        # Merge existing with new
        activities[activity_index].update(new_activity)
    else:
        raise ValueError(f"Unknown action: {action}")

    days[idx]["activities"] = activities
    return result


def update_accommodation(
    proposal: Dict[str, Any],
    day_number: int,
    accommodation: Dict[str, Any],
    apply_to_consecutive: bool = False,
) -> Dict[str, Any]:
    """
    Update accommodation for a day.

    Args:
        proposal: The proposal dict to modify
        day_number: Day to update (1-indexed)
        accommodation: New accommodation dict
        apply_to_consecutive: Apply to consecutive days with same accommodation

    Returns:
        Modified proposal dict
    """
    result = copy.deepcopy(proposal)
    days = result.get("days", [])

    idx = day_number - 1
    if idx < 0 or idx >= len(days):
        raise ValueError(f"Day {day_number} is out of range (1-{len(days)})")

    old_accommodation = days[idx].get("accommodation")
    days[idx]["accommodation"] = accommodation

    # Optionally apply to consecutive days with the same accommodation
    if apply_to_consecutive and old_accommodation:
        old_name = old_accommodation.get("name")

        # Check forward
        for i in range(idx + 1, len(days)):
            if days[i].get("accommodation", {}).get("name") == old_name:
                days[i]["accommodation"] = copy.deepcopy(accommodation)
            else:
                break

        # Check backward
        for i in range(idx - 1, -1, -1):
            if days[i].get("accommodation", {}).get("name") == old_name:
                days[i]["accommodation"] = copy.deepcopy(accommodation)
            else:
                break

    return result


def _renumber_days(days: List[Dict[str, Any]], start_date: Optional[str] = None) -> None:
    """
    Renumber days and recalculate dates in place.

    Args:
        days: List of day dicts to modify
        start_date: Starting date (YYYY-MM-DD format)
    """
    base_date = None
    if start_date:
        try:
            base_date = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            pass

    for i, day in enumerate(days):
        day["day_number"] = i + 1
        if base_date:
            day_date = base_date + timedelta(days=i)
            day["date"] = day_date.strftime("%Y-%m-%d")


# ============================================================================
# Tool Execution Router
# ============================================================================


def execute_tool(tool_name: str, tool_input: Dict[str, Any], proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a refinement tool on a proposal.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
        proposal: The proposal dict to modify

    Returns:
        Modified proposal dict

    Raises:
        ValueError: If tool_name is unknown or execution fails
    """
    if tool_name == "swap_days":
        return swap_days(
            proposal,
            tool_input["day_a"],
            tool_input["day_b"],
            tool_input.get("reason", ""),
        )
    elif tool_name == "add_day":
        return add_day(
            proposal,
            tool_input["after_day"],
            tool_input["title"],
            tool_input["location"],
            tool_input["activities"],
            tool_input.get("accommodation"),
            tool_input.get("notes", ""),
        )
    elif tool_name == "remove_day":
        return remove_day(
            proposal,
            tool_input["day_number"],
            tool_input.get("reason", ""),
        )
    elif tool_name == "update_activity":
        return update_activity(
            proposal,
            tool_input["day_number"],
            tool_input["activity_index"],
            tool_input["action"],
            tool_input.get("new_activity"),
        )
    elif tool_name == "update_accommodation":
        return update_accommodation(
            proposal,
            tool_input["day_number"],
            tool_input["accommodation"],
            tool_input.get("apply_to_consecutive", False),
        )
    else:
        raise ValueError(f"Unknown tool: {tool_name}")


# ============================================================================
# Streaming Refinement with Claude
# ============================================================================


def build_refinement_system_prompt(proposal: Dict[str, Any]) -> str:
    """Build system prompt for refinement with full itinerary context."""
    return f"""You are a travel planning assistant helping refine an existing itinerary.

CURRENT ITINERARY:
{json.dumps(proposal, indent=2)}

Your job is to help the user make modifications to this itinerary through natural conversation.
You have access to tools for:
- swap_days: Reorder days in the itinerary
- add_day: Insert new days (rest days, extensions, etc.)
- remove_day: Remove days to shorten the trip
- update_activity: Modify, replace, or remove specific activities
- update_accommodation: Change where the traveler stays

When the user asks for changes:
1. Understand what they want to achieve
2. Use the appropriate tool(s) to make the change
3. Explain what you did and how it affects the itinerary

Guidelines:
- Always maintain consistency (dates, day numbers, logical flow)
- When adding rest days, use the same accommodation as the previous night
- Consider practical implications (travel time, booking requirements)
- Be proactive about mentioning any caveats or considerations

If the user's request is unclear, ask clarifying questions before making changes."""


async def refine_itinerary_streaming(
    proposal: Dict[str, Any],
    messages: List[Dict[str, str]],
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream refinement responses with tool execution.

    Yields events:
    - {"type": "text", "content": "..."} - Text chunks
    - {"type": "tool_use", "name": "...", "input": {...}} - Tool being used
    - {"type": "tool_result", "name": "...", "success": bool, "proposal": {...}} - Tool result
    - {"type": "done", "proposal": {...}, "usage": {...}} - Final state

    Args:
        proposal: Current proposal dict
        messages: Conversation messages

    Yields:
        Event dicts
    """
    system_prompt = build_refinement_system_prompt(proposal)
    current_proposal = copy.deepcopy(proposal)

    # Stream response from Claude
    async with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
        tools=REFINEMENT_TOOLS,
    ) as stream:
        tool_inputs: Dict[str, str] = {}
        tool_names: Dict[str, str] = {}
        current_tool_id = None

        async for event in stream:
            if event.type == "content_block_start":
                if hasattr(event.content_block, "type"):
                    if event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        tool_inputs[current_tool_id] = ""
                        tool_names[current_tool_id] = event.content_block.name

            elif event.type == "content_block_delta":
                if hasattr(event.delta, "text"):
                    yield {"type": "text", "content": event.delta.text}
                elif hasattr(event.delta, "partial_json"):
                    if current_tool_id:
                        tool_inputs[current_tool_id] += event.delta.partial_json

            elif event.type == "content_block_stop":
                if current_tool_id and current_tool_id in tool_inputs:
                    tool_name = tool_names[current_tool_id]
                    try:
                        tool_input = json.loads(tool_inputs[current_tool_id])

                        yield {
                            "type": "tool_use",
                            "name": tool_name,
                            "input": tool_input,
                        }

                        # Execute the tool
                        current_proposal = execute_tool(tool_name, tool_input, current_proposal)

                        yield {
                            "type": "tool_result",
                            "name": tool_name,
                            "success": True,
                            "proposal": current_proposal,
                        }

                    except Exception as e:
                        yield {
                            "type": "tool_result",
                            "name": tool_name,
                            "success": False,
                            "error": str(e),
                        }

                    current_tool_id = None

        final_message = await stream.get_final_message()
        yield {
            "type": "done",
            "proposal": current_proposal,
            "usage": {
                "input_tokens": final_message.usage.input_tokens,
                "output_tokens": final_message.usage.output_tokens,
            },
        }
