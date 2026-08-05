"""Logistics specialist agent."""

import json
from typing import Any, AsyncGenerator, Dict, List

from app.agents.base_agent import (
    BaseAgent,
    SectionHandoff,
    SectionResult,
    CrossSectionImpact,
)
from app.prompts.agent_prompts import LOGISTICS_AGENT_PROMPT, LOGISTICS_GENERATION_PROMPT


class LogisticsAgent(BaseAgent):
    """Specialized agent for logistics and overview section management."""

    SECTION_TYPE = "logistics"
    SYSTEM_PROMPT = LOGISTICS_AGENT_PROMPT

    TOOLS = [
        {
            "name": "update_overview",
            "description": "Update the trip overview section",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Itinerary title/theme",
                    },
                    "summary": {
                        "type": "string",
                        "description": "2-3 sentence overview",
                    },
                    "highlights": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Top trip highlights",
                    },
                    "total_budget_estimate": {
                        "type": "string",
                        "description": "Total trip cost range",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes",
                    },
                },
            },
        },
        {
            "name": "add_transportation_note",
            "description": "Add a ground transportation note",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "Transportation information",
                    },
                },
                "required": ["note"],
            },
        },
        {
            "name": "add_packing_suggestion",
            "description": "Add a packing suggestion",
            "input_schema": {
                "type": "object",
                "properties": {
                    "item": {
                        "type": "string",
                        "description": "What to pack",
                    },
                },
                "required": ["item"],
            },
        },
        {
            "name": "add_booking_requirement",
            "description": "Add a booking requirement or deadline",
            "input_schema": {
                "type": "object",
                "properties": {
                    "requirement": {
                        "type": "string",
                        "description": "Booking requirement",
                    },
                },
                "required": ["requirement"],
            },
        },
        {
            "name": "set_visa_requirements",
            "description": "Set visa/entry requirements",
            "input_schema": {
                "type": "object",
                "properties": {
                    "requirements": {
                        "type": "string",
                        "description": "Visa and entry requirements",
                    },
                },
                "required": ["requirements"],
            },
        },
        {
            "name": "add_health_note",
            "description": "Add a health or vaccination note",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "Health/vaccination information",
                    },
                },
                "required": ["note"],
            },
        },
        {
            "name": "add_caveat",
            "description": "Add a caveat or consideration",
            "input_schema": {
                "type": "object",
                "properties": {
                    "caveat": {
                        "type": "string",
                        "description": "Something to consider or watch out for",
                    },
                },
                "required": ["caveat"],
            },
        },
        {
            "name": "update_logistics_section",
            "description": "Update the full logistics section",
            "input_schema": {
                "type": "object",
                "properties": {
                    "transportation_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ground transportation info",
                    },
                    "packing_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "What to pack",
                    },
                    "booking_requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Things to book in advance",
                    },
                    "visa_requirements": {
                        "type": "string",
                        "description": "Visa/entry requirements",
                    },
                    "health_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Health/vaccination info",
                    },
                    "caveats": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Things to consider",
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
                        "enum": ["overview", "flights", "accommodations", "activities"],
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
        self.overview_updates: Dict[str, Any] = {}

    def _is_generation_mode(self, handoff: SectionHandoff) -> bool:
        """Check if this is initial generation (vs refinement)."""
        # Generation mode if:
        # 1. is_generation flag in constraints, OR
        # 2. Current state has no logistics content
        if "is_generation" in handoff.constraints:
            return True
        # Check if logistics section is effectively empty
        has_transport = bool(handoff.current_state.get("transportation_notes", []))
        has_packing = bool(handoff.current_state.get("packing_suggestions", []))
        has_caveats = bool(handoff.current_state.get("caveats", []))
        return not (has_transport or has_packing or has_caveats)

    def _build_system_prompt(self, handoff: SectionHandoff) -> str:
        """Build context-aware system prompt with mode detection."""
        base_prompt = (
            LOGISTICS_GENERATION_PROMPT
            if self._is_generation_mode(handoff)
            else LOGISTICS_AGENT_PROMPT
        )

        prompt_parts = [base_prompt]

        # Add current section state
        prompt_parts.append(f"\nCURRENT SECTION STATE:\n{handoff.current_state}")

        # Add activities context for logistics planning
        if handoff.related_sections and "activities" in handoff.related_sections:
            activities = handoff.related_sections["activities"]
            if activities.get("days"):
                prompt_parts.append(f"\nACTIVITIES PLANNED: {len(activities['days'])} days")
                locations = set(d.get("location", "") for d in activities["days"] if d.get("location"))
                if locations:
                    prompt_parts.append(f"LOCATIONS: {', '.join(locations)}")

        # Add constraints from other sections
        if handoff.constraints:
            constraints_text = "\n".join(f"- {c}" for c in handoff.constraints if c != "is_generation")
            if constraints_text:
                prompt_parts.append(f"\nCONSTRAINTS FROM OTHER SECTIONS:\n{constraints_text}")

        # Add user preferences
        if handoff.preferences:
            prompt_parts.append(f"\nTRAVELER PREFERENCES:\n{handoff.preferences}")

        return "\n".join(prompt_parts)

    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a logistics tool."""
        if tool_name == "update_overview":
            self.overview_updates.update(tool_input)
            return {"status": "overview_updated", "updates": tool_input}

        elif tool_name == "add_transportation_note":
            if "transportation_notes" not in self.current_section_state:
                self.current_section_state["transportation_notes"] = []
            self.current_section_state["transportation_notes"].append(
                tool_input["note"]
            )
            return {"status": "added", "note": tool_input["note"]}

        elif tool_name == "add_packing_suggestion":
            if "packing_suggestions" not in self.current_section_state:
                self.current_section_state["packing_suggestions"] = []
            self.current_section_state["packing_suggestions"].append(tool_input["item"])
            return {"status": "added", "item": tool_input["item"]}

        elif tool_name == "add_booking_requirement":
            if "booking_requirements" not in self.current_section_state:
                self.current_section_state["booking_requirements"] = []
            self.current_section_state["booking_requirements"].append(
                tool_input["requirement"]
            )
            return {"status": "added", "requirement": tool_input["requirement"]}

        elif tool_name == "set_visa_requirements":
            self.current_section_state["visa_requirements"] = tool_input["requirements"]
            return {"status": "set", "requirements": tool_input["requirements"]}

        elif tool_name == "add_health_note":
            if "health_notes" not in self.current_section_state:
                self.current_section_state["health_notes"] = []
            self.current_section_state["health_notes"].append(tool_input["note"])
            return {"status": "added", "note": tool_input["note"]}

        elif tool_name == "add_caveat":
            if "caveats" not in self.current_section_state:
                self.current_section_state["caveats"] = []
            self.current_section_state["caveats"].append(tool_input["caveat"])
            return {"status": "added", "caveat": tool_input["caveat"]}

        elif tool_name == "update_logistics_section":
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
        """Process a logistics section request."""
        self.current_section_state = handoff.current_state.copy()
        self.cross_section_impacts = []
        self.overview_updates = {}

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

        # Include overview updates in the result
        if self.overview_updates:
            self.current_section_state["_overview_updates"] = self.overview_updates

        # Final result
        final_result = SectionResult(
            section_type=self.SECTION_TYPE,
            updated_state=self.current_section_state,
            changes_made=changes_made,
            cross_section_impacts=self.cross_section_impacts,
        )
        yield {"type": "done", "result": final_result.model_dump()}


__all__ = ["LogisticsAgent"]
