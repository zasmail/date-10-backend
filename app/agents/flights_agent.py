"""Flights specialist agent."""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.agents.base_agent import (
    BaseAgent,
    SectionHandoff,
    SectionResult,
    CrossSectionImpact,
)
from app.prompts.agent_prompts import FLIGHTS_AGENT_PROMPT, FLIGHTS_GENERATION_PROMPT
from app.schemas.flight import FlightSearchRequest, FlightSegmentRequest


class FlightsAgent(BaseAgent):
    """Specialized agent for flight section management."""

    SECTION_TYPE = "flights"
    SYSTEM_PROMPT = FLIGHTS_AGENT_PROMPT

    TOOLS = [
        {
            "name": "search_segment_flights",
            "description": "Search for flight options for a single journey segment",
            "input_schema": {
                "type": "object",
                "properties": {
                    "segment_id": {
                        "type": "integer",
                        "description": "Segment number (1, 2, 3...)",
                    },
                    "origin": {
                        "type": "string",
                        "description": "Origin city or IATA code",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination city or IATA code",
                    },
                    "date": {
                        "type": "string",
                        "description": "Departure date YYYY-MM-DD",
                    },
                    "num_travelers": {"type": "integer", "default": 1},
                    "cabin_class": {
                        "type": "string",
                        "enum": ["E", "B", "F"],
                        "default": "E",
                    },
                },
                "required": ["segment_id", "origin", "destination", "date"],
            },
        },
        {
            "name": "select_segment_flight",
            "description": "Select a flight option for a specific segment",
            "input_schema": {
                "type": "object",
                "properties": {
                    "segment_id": {
                        "type": "integer",
                        "description": "Which segment (1, 2, 3...)",
                    },
                    "option_id": {
                        "type": "string",
                        "description": "Flight option ID to select",
                    },
                },
                "required": ["segment_id", "option_id"],
            },
        },
        {
            "name": "update_flights_section",
            "description": "Update the flights section with search results and calculate totals",
            "input_schema": {
                "type": "object",
                "properties": {
                    "segments": {
                        "type": "array",
                        "description": "List of segment objects with options",
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
                        "enum": ["overview", "accommodations", "activities", "logistics"],
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
        self._search_results: Dict[int, Dict[str, Any]] = {}  # Track search results by segment_id

    def _is_generation_mode(self, handoff: SectionHandoff) -> bool:
        """Check if this is initial generation vs refinement."""
        if "is_generation" in handoff.constraints:
            return True
        segments = handoff.current_state.get("segments", [])
        return len(segments) == 0

    def _build_system_prompt(self, handoff: SectionHandoff) -> str:
        """Build context-aware system prompt."""
        base_prompt = (
            FLIGHTS_GENERATION_PROMPT
            if self._is_generation_mode(handoff)
            else FLIGHTS_AGENT_PROMPT
        )
        context_parts = [base_prompt]

        if handoff.related_sections.get("overview"):
            overview = handoff.related_sections["overview"]
            context_parts.append("\nITINERARY CONTEXT:")
            context_parts.append(f"- Destination: {overview.get('destination', 'Unknown')}")
            context_parts.append(f"- Dates: {overview.get('start_date')} to {overview.get('end_date')}")
            context_parts.append(f"- Travelers: {overview.get('num_travelers', 1)}")

        if handoff.current_state.get("segments"):
            context_parts.append(f"\nCURRENT SEGMENTS: {len(handoff.current_state['segments'])} segment(s)")

        return "\n".join(context_parts)

    def _convert_api_to_segment_options(self, options: List[Any]) -> List[Dict[str, Any]]:
        """Convert Trip Ninja API response to FlightSegmentOption format."""
        segment_options = []
        for opt in options:
            legs = []
            for seg in opt.segments:
                for flight in seg.flights:
                    legs.append({
                        "departure_airport": flight.departure_airport,
                        "arrival_airport": flight.arrival_airport,
                        "departure_time": flight.departure_time,
                        "arrival_time": flight.arrival_time,
                        "airline": flight.airline,
                        "flight_number": flight.flight_number,
                        "duration_minutes": flight.duration_minutes,
                        "operating_airline": flight.operating_airline,
                    })
            segment_options.append({
                "id": opt.id,
                "legs": legs,
                "total_price": opt.total_price,
                "price_per_person": opt.price_per_person,
                "currency": opt.currency,
                "is_virtual_interlining": opt.is_virtual_interlining,
                "warnings": opt.warnings,
                "booking_url": opt.booking_url,
            })
        return segment_options

    def _calculate_price_range(self, segments: List[Dict[str, Any]]) -> str:
        """Calculate overall price range from segment options."""
        min_total = 0.0
        max_total = 0.0
        for seg in segments:
            options = seg.get("options", [])
            if options:
                prices = [o.get("total_price", 0) for o in options]
                min_total += min(prices)
                max_total += max(prices)
        if min_total == max_total:
            return f"${int(min_total)}"
        return f"${int(min_total)}-${int(max_total)}"

    def _calculate_total_price(self, segments: List[Dict[str, Any]]) -> Optional[float]:
        """Calculate total price from selected or best options."""
        total = 0.0
        for seg in segments:
            selected_id = seg.get("selected_option_id") or seg.get("best_option_id")
            if selected_id:
                for opt in seg.get("options", []):
                    if opt.get("id") == selected_id:
                        total += opt.get("total_price", 0)
                        break
        return total if total > 0 else None

    async def execute_tool_async(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute flights tool with real API calls."""
        # Lazy import to avoid circular import with orchestrator
        from app.services.flight_service import search_flights as api_search_flights
        from app.services.flight_service import get_iata_code

        if tool_name == "search_segment_flights":
            origin_iata = get_iata_code(tool_input["origin"]) or tool_input["origin"].upper()
            dest_iata = get_iata_code(tool_input["destination"]) or tool_input["destination"].upper()

            # Store this segment request for batching
            if not hasattr(self, '_pending_segments'):
                self._pending_segments = {}

            self._pending_segments[tool_input["segment_id"]] = {
                "id": tool_input["segment_id"],
                "origin": origin_iata,
                "destination": dest_iata,
                "date": tool_input["date"],
                "cabin_class": tool_input.get("cabin_class", "E"),
                "num_travelers": tool_input.get("num_travelers", 1),
            }

            # Build FlightSearchRequest with ALL accumulated segments (1-indexed, sorted)
            all_segments = []
            for seg_id in sorted(self._pending_segments.keys()):
                seg_data = self._pending_segments[seg_id]
                all_segments.append(FlightSegmentRequest(
                    id=seg_id,  # Keep original segment ID
                    departure_date=seg_data["date"],
                    cabin_class=seg_data["cabin_class"],
                    from_iata=seg_data["origin"],
                    to_iata=seg_data["destination"],
                    from_type="C",
                    to_type="C",
                ))

            request = FlightSearchRequest(
                segments=all_segments,  # Send ALL segments together
                travellers=["ADT"] * tool_input.get("num_travelers", 1),
                currency="USD",
                virtual_interlining=True,
            )

            result = await api_search_flights(request)
            options = self._convert_api_to_segment_options(result.options)

            # Auto-select best (cheapest)
            best_id = options[0]["id"] if options else None

            # Store search result for this segment
            segment_data = {
                "id": tool_input["segment_id"],
                "origin": origin_iata,
                "destination": dest_iata,
                "date": tool_input["date"],
                "cabin_class": tool_input.get("cabin_class", "E"),
                "options": options,
                "selected_option_id": None,
                "best_option_id": best_id,
            }
            self._search_results[tool_input["segment_id"]] = segment_data

            # AUTO-SAVE: Update state with all accumulated segments
            segments_list = [self._search_results[sid] for sid in sorted(self._search_results.keys())]
            price_range = self._calculate_price_range(segments_list)
            total_price = self._calculate_total_price(segments_list)

            self.current_section_state.update({
                "segments": segments_list,
                "total_price": total_price,
                "price_range": price_range,
                "searched_at": datetime.utcnow().isoformat(),
            })

            return {
                "status": "search_complete",
                "segment_id": tool_input["segment_id"],
                "origin": origin_iata,
                "destination": dest_iata,
                "date": tool_input["date"],
                "options_count": len(options),
                "options": options,
                "best_option_id": best_id,
                "price_range": result.price_range,
                "auto_saved": True,  # Indicate that results were automatically saved
            }

        elif tool_name == "select_segment_flight":
            segment_id = tool_input["segment_id"]
            option_id = tool_input["option_id"]

            segments = self.current_section_state.get("segments", [])
            for seg in segments:
                if seg.get("id") == segment_id:
                    seg["selected_option_id"] = option_id
                    break

            self.current_section_state["segments"] = segments
            # Recalculate totals after selection
            self.current_section_state["total_price"] = self._calculate_total_price(segments)
            return {"status": "selected", "segment_id": segment_id, "option_id": option_id}

        elif tool_name == "update_flights_section":
            segments = tool_input.get("segments", [])
            # Calculate price_range and total_price from segment data
            price_range = self._calculate_price_range(segments)
            total_price = self._calculate_total_price(segments)

            self.current_section_state.update({
                "segments": segments,
                "total_price": total_price,
                "price_range": price_range,
                "searched_at": datetime.utcnow().isoformat(),
            })
            return {
                "status": "updated",
                "segment_count": len(segments),
                "price_range": price_range,
                "total_price": total_price,
            }

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

    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a flights tool (sync version for backward compatibility)."""
        # Legacy tool handling for backward compatibility
        if tool_name == "search_flights":
            return {"status": "search_initiated", "params": tool_input}

        elif tool_name == "select_flight":
            flight_type = tool_input["flight_type"]
            flight_id = tool_input["flight_id"]
            if flight_type == "outbound":
                self.current_section_state["selected_outbound_id"] = flight_id
            else:
                self.current_section_state["selected_return_id"] = flight_id
            return {
                "status": "selected",
                "flight_type": flight_type,
                "flight_id": flight_id,
            }

        elif tool_name == "update_flights_section":
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
        """Process a flights section request."""
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

                            result = await self.execute_tool_async(tool_name, tool_input)
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


__all__ = ["FlightsAgent"]
