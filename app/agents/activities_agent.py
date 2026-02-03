"""Activities specialist agent."""

import json
from typing import Any, AsyncGenerator, Dict, List

from app.agents.base_agent import (
    BaseAgent,
    SectionHandoff,
    SectionResult,
    CrossSectionImpact,
)
from app.prompts.agent_prompts import ACTIVITIES_AGENT_PROMPT, ACTIVITIES_GENERATION_PROMPT


class ActivitiesAgent(BaseAgent):
    """Specialized agent for activities section management."""

    SECTION_TYPE = "activities"
    SYSTEM_PROMPT = ACTIVITIES_AGENT_PROMPT

    TOOLS = [
        {
            "name": "search_operators",
            "description": "OPTIONAL: Search for local operators and guides for activities. Use this to research before creating the schedule, but you MUST still call update_activities_section afterward.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destination to search operators for",
                    },
                    "activity_type": {
                        "type": "string",
                        "description": "Type of activity (kitesurfing, diving, trekking, etc.)",
                    },
                    "month": {
                        "type": "string",
                        "description": "Travel month for seasonality check",
                    },
                },
                "required": ["destination"],
            },
        },
        {
            "name": "add_activity",
            "description": "Add an activity to a specific day",
            "input_schema": {
                "type": "object",
                "properties": {
                    "day_number": {
                        "type": "integer",
                        "description": "Day number to add activity to",
                    },
                    "time": {
                        "type": "string",
                        "description": "Time of day (e.g., '09:00', 'morning')",
                    },
                    "name": {
                        "type": "string",
                        "description": "Activity name",
                    },
                    "description": {
                        "type": "string",
                        "description": "What this activity involves",
                    },
                    "duration": {
                        "type": "string",
                        "description": "How long (e.g., '2 hours')",
                    },
                    "location": {
                        "type": "string",
                        "description": "Specific location",
                    },
                    "cost_estimate": {
                        "type": "string",
                        "description": "Price range (e.g., '$50-80')",
                    },
                    "operator": {
                        "type": "string",
                        "description": "Local operator/guide name",
                    },
                    "booking_required": {
                        "type": "boolean",
                        "description": "Whether advance booking is needed",
                    },
                },
                "required": ["day_number", "time", "name", "description", "duration"],
            },
        },
        {
            "name": "update_day",
            "description": "Update a full day's schedule",
            "input_schema": {
                "type": "object",
                "properties": {
                    "day_number": {
                        "type": "integer",
                        "description": "Day number to update",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date (YYYY-MM-DD)",
                    },
                    "title": {
                        "type": "string",
                        "description": "Day title",
                    },
                    "location": {
                        "type": "string",
                        "description": "Primary location for this day",
                    },
                    "activities": {
                        "type": "array",
                        "description": "List of activities for the day",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "string"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "duration": {"type": "string"},
                                "location": {"type": "string"},
                                "cost_estimate": {"type": "string"},
                                "operator": {"type": "string"},
                                "booking_required": {"type": "boolean"},
                            },
                        },
                    },
                    "notes": {
                        "type": "string",
                        "description": "Day-specific notes",
                    },
                },
                "required": ["day_number", "date", "title", "location"],
            },
        },
        {
            "name": "update_activities_section",
            "description": "REQUIRED: Submit the complete day-by-day activities schedule. Use this to create or replace the entire activities section with a full days array. This is the PRIMARY tool for building itineraries.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "array",
                        "description": "Complete array of all activity days with day_number, date, title, location, and activities list for each day",
                    },
                    "total_activities_cost": {
                        "type": "string",
                        "description": "Estimated total activities cost (e.g., '$500-800')",
                    },
                },
                "required": ["days"],
            },
        },
        {
            "name": "report_cross_section_impact",
            "description": "Report an impact that affects other sections",
            "input_schema": {
                "type": "object",
                "properties": {
                    "affected_section": {
                        "type": "string",
                        "enum": ["overview", "flights", "accommodations", "logistics"],
                    },
                    "impact_type": {"type": "string"},
                    "description": {"type": "string"},
                    "suggested_action": {"type": "string"},
                },
                "required": ["affected_section", "impact_type", "description"],
            },
        },
    ]

    def __init__(self):
        super().__init__()
        self.cross_section_impacts: List[CrossSectionImpact] = []
        self.current_section_state: Dict[str, Any] = {}

    def _is_generation_mode(self, handoff: SectionHandoff) -> bool:
        """Check if this is initial generation (vs refinement)."""
        # Generation mode if:
        # 1. is_generation flag in constraints, OR
        # 2. Current state has no days (empty activities section)
        if "is_generation" in handoff.constraints:
            return True
        current_days = handoff.current_state.get("days", [])
        return len(current_days) == 0

    def _build_system_prompt(self, handoff: SectionHandoff) -> str:
        """Build context-aware system prompt with mode detection."""
        base_prompt = (
            ACTIVITIES_GENERATION_PROMPT
            if self._is_generation_mode(handoff)
            else ACTIVITIES_AGENT_PROMPT
        )

        prompt_parts = [base_prompt]

        # Add current section state
        prompt_parts.append(f"\nCURRENT SECTION STATE:\n{handoff.current_state}")

        # Add constraints from other sections
        if handoff.constraints:
            constraints_text = "\n".join(f"- {c}" for c in handoff.constraints if c != "is_generation")
            if constraints_text:
                prompt_parts.append(f"\nCONSTRAINTS FROM OTHER SECTIONS:\n{constraints_text}")

        # Add related section data
        if handoff.related_sections:
            prompt_parts.append(f"\nRELATED SECTION DATA:\n{handoff.related_sections}")

        # Add user preferences
        if handoff.preferences:
            prompt_parts.append(f"\nTRAVELER PREFERENCES:\n{handoff.preferences}")

        return "\n".join(prompt_parts)

    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an activities tool."""
        if tool_name == "search_operators":
            # Return search params; actual search would use operator knowledge
            return {"status": "search_initiated", "params": tool_input}

        elif tool_name == "add_activity":
            day_number = tool_input["day_number"]
            if "days" not in self.current_section_state:
                self.current_section_state["days"] = []

            # Find or create the day
            day_found = False
            for day in self.current_section_state["days"]:
                if day.get("day_number") == day_number:
                    if "activities" not in day:
                        day["activities"] = []
                    day["activities"].append(
                        {
                            "time": tool_input["time"],
                            "name": tool_input["name"],
                            "description": tool_input["description"],
                            "duration": tool_input["duration"],
                            "location": tool_input.get("location"),
                            "cost_estimate": tool_input.get("cost_estimate"),
                            "operator": tool_input.get("operator"),
                            "booking_required": tool_input.get("booking_required", False),
                        }
                    )
                    day_found = True
                    break

            if not day_found:
                # Create new day
                self.current_section_state["days"].append(
                    {
                        "day_number": day_number,
                        "date": "",
                        "title": "",
                        "location": "",
                        "activities": [
                            {
                                "time": tool_input["time"],
                                "name": tool_input["name"],
                                "description": tool_input["description"],
                                "duration": tool_input["duration"],
                                "location": tool_input.get("location"),
                                "cost_estimate": tool_input.get("cost_estimate"),
                                "operator": tool_input.get("operator"),
                                "booking_required": tool_input.get(
                                    "booking_required", False
                                ),
                            }
                        ],
                        "notes": "",
                    }
                )

            return {
                "status": "added",
                "day_number": day_number,
                "activity": tool_input["name"],
            }

        elif tool_name == "update_day":
            day_number = tool_input["day_number"]
            if "days" not in self.current_section_state:
                self.current_section_state["days"] = []

            # Find and update or add the day
            day_found = False
            for i, day in enumerate(self.current_section_state["days"]):
                if day.get("day_number") == day_number:
                    self.current_section_state["days"][i] = {
                        "day_number": day_number,
                        "date": tool_input["date"],
                        "title": tool_input["title"],
                        "location": tool_input["location"],
                        "activities": tool_input.get("activities", []),
                        "notes": tool_input.get("notes", ""),
                    }
                    day_found = True
                    break

            if not day_found:
                self.current_section_state["days"].append(
                    {
                        "day_number": day_number,
                        "date": tool_input["date"],
                        "title": tool_input["title"],
                        "location": tool_input["location"],
                        "activities": tool_input.get("activities", []),
                        "notes": tool_input.get("notes", ""),
                    }
                )

            return {"status": "updated", "day_number": day_number}

        elif tool_name == "update_activities_section":
            self.current_section_state.update(tool_input)
            return {"status": "updated", "section": self.current_section_state}

        elif tool_name == "report_cross_section_impact":
            impact = self._report_cross_section_impact(
                affected_section=tool_input["affected_section"],
                impact_type=tool_input["impact_type"],
                description=tool_input["description"],
                suggested_action=tool_input.get("suggested_action"),
            )
            self.cross_section_impacts.append(impact)
            return {"status": "impact_recorded", "impact": impact.model_dump()}

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def process(
        self,
        handoff: SectionHandoff,
        messages: List[Dict[str, str]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process an activities section request."""
        self.current_section_state = handoff.current_state.copy()
        self.cross_section_impacts = []

        system_prompt = self._build_system_prompt(handoff)
        changes_made = []

        async with self.client.messages.stream(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=self.TOOLS,
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

                            result = self.execute_tool(tool_name, tool_input)
                            changes_made.append(
                                f"{tool_name}: {result.get('status', 'executed')}"
                            )

                            yield {
                                "type": "tool_result",
                                "name": tool_name,
                                "result": result,
                            }
                        except json.JSONDecodeError as e:
                            yield {"type": "error", "message": f"JSON parse error: {e}"}
                        except Exception as e:
                            yield {"type": "error", "message": str(e)}

                        current_tool_id = None

        # Final result
        final_result = SectionResult(
            section_type=self.SECTION_TYPE,
            updated_state=self.current_section_state,
            changes_made=changes_made,
            cross_section_impacts=self.cross_section_impacts,
        )
        yield {"type": "done", "result": final_result.model_dump()}


__all__ = ["ActivitiesAgent"]
