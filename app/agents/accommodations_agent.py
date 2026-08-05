"""Accommodations specialist agent."""

import json
from typing import Any, AsyncGenerator, Dict, List

from app.agents.base_agent import (
    BaseAgent,
    SectionHandoff,
    SectionResult,
    CrossSectionImpact,
)
from app.prompts.agent_prompts import ACCOMMODATIONS_AGENT_PROMPT


class AccommodationsAgent(BaseAgent):
    """Specialized agent for accommodation section management."""

    SECTION_TYPE = "accommodations"
    SYSTEM_PROMPT = ACCOMMODATIONS_AGENT_PROMPT

    TOOLS = [
        {
            "name": "search_accommodations",
            "description": "Search for accommodation options in a destination",
            "input_schema": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destination to search accommodations for",
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date (YYYY-MM-DD)",
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date (YYYY-MM-DD)",
                    },
                    "style_preference": {
                        "type": "string",
                        "description": "Preferred style (boutique, surf camp, eco-lodge, etc.)",
                    },
                    "max_price_per_night": {
                        "type": "number",
                        "description": "Maximum price per night in USD",
                    },
                },
                "required": ["destination", "check_in", "check_out"],
            },
        },
        {
            "name": "select_accommodation",
            "description": "Select an accommodation for specific nights",
            "input_schema": {
                "type": "object",
                "properties": {
                    "accommodation_name": {
                        "type": "string",
                        "description": "Name of the accommodation",
                    },
                    "dates": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Dates to book (YYYY-MM-DD format)",
                    },
                },
                "required": ["accommodation_name", "dates"],
            },
        },
        {
            "name": "update_accommodations_section",
            "description": "Update the accommodations section with new data",
            "input_schema": {
                "type": "object",
                "properties": {
                    "nights": {
                        "type": "array",
                        "description": "List of accommodation nights",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string"},
                                "name": {"type": "string"},
                                "area": {"type": "string"},
                                "style": {"type": "string"},
                                "price_range": {"type": "string"},
                                "notes": {"type": "string"},
                            },
                        },
                    },
                    "total_accommodation_cost": {
                        "type": "string",
                        "description": "Estimated total cost for all nights",
                    },
                },
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
                        "enum": ["overview", "flights", "activities", "logistics"],
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

    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an accommodations tool."""
        if tool_name == "search_accommodations":
            # Return search params; actual search would use accommodation knowledge
            return {"status": "search_initiated", "params": tool_input}

        elif tool_name == "select_accommodation":
            accommodation_name = tool_input["accommodation_name"]
            dates = tool_input["dates"]
            # Add nights to current state
            if "nights" not in self.current_section_state:
                self.current_section_state["nights"] = []

            for date in dates:
                self.current_section_state["nights"].append(
                    {
                        "date": date,
                        "name": accommodation_name,
                        "area": "",
                        "style": "",
                        "price_range": "",
                        "notes": "",
                    }
                )
            return {
                "status": "selected",
                "accommodation": accommodation_name,
                "dates": dates,
            }

        elif tool_name == "update_accommodations_section":
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
        """Process an accommodations section request."""
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


__all__ = ["AccommodationsAgent"]
