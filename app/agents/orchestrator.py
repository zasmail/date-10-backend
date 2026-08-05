"""Orchestrator agent for coordinating specialized section agents."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field

from anthropic import AsyncAnthropic

from app.agents.base_agent import SectionHandoff, SectionResult, CrossSectionImpact
from app.agents.flights_agent import FlightsAgent
from app.agents.accommodations_agent import AccommodationsAgent
from app.agents.activities_agent import ActivitiesAgent
from app.agents.logistics_agent import LogisticsAgent
from app.schemas.itinerary_sections import (
    SectionedItinerary,
    OverviewSection,
    FlightsSection,
    AccommodationsSection,
    ActivitiesSection,
    LogisticsSection,
)


class IntentClassification(BaseModel):
    """Classification of user request intent."""

    primary_section: str = Field(
        ...,
        description="Main section affected: overview, flights, accommodations, activities, logistics",
    )
    secondary_sections: List[str] = Field(
        default_factory=list,
        description="Other sections that may need updates",
    )
    action_type: str = Field(
        ...,
        description="Type of action: search, update, remove, compare, clarify",
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in classification (0-1)",
    )
    clarification_needed: Optional[str] = Field(
        None,
        description="Question to ask user if confidence < 0.7",
    )


class ConsistencyIssue(BaseModel):
    """A consistency issue between sections."""

    issue_type: str
    description: str
    affected_sections: List[str]
    suggested_fix: Optional[str] = None
    severity: str = "warning"  # warning, error


class ValidationResult(BaseModel):
    """Result of cross-section consistency validation."""

    is_valid: bool
    issues: List[ConsistencyIssue] = Field(default_factory=list)


class OrchestratorResult(BaseModel):
    """Result from orchestrator processing."""

    itinerary: SectionedItinerary
    sections_updated: List[str]
    agent_responses: List[SectionResult]
    validation_result: ValidationResult
    text_response: str = ""


# Tool for intent classification
INTENT_CLASSIFICATION_TOOL = {
    "name": "classify_intent",
    "description": "Classify which sections are affected by the user's request",
    "input_schema": {
        "type": "object",
        "properties": {
            "primary_section": {
                "type": "string",
                "enum": [
                    "overview",
                    "flights",
                    "accommodations",
                    "activities",
                    "logistics",
                ],
                "description": "Main section affected by the request",
            },
            "secondary_sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Other sections that may need updates",
            },
            "action_type": {
                "type": "string",
                "enum": ["search", "update", "remove", "compare", "clarify"],
                "description": "Type of action requested",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in this classification (0-1)",
            },
            "clarification_needed": {
                "type": "string",
                "description": "Question to ask if request is ambiguous",
            },
        },
        "required": ["primary_section", "action_type", "confidence"],
    },
}


class ItineraryOrchestrator:
    """Coordinates specialized section agents based on user intent."""

    SECTION_AGENTS = {
        "flights": FlightsAgent,
        "accommodations": AccommodationsAgent,
        "activities": ActivitiesAgent,
        "logistics": LogisticsAgent,
    }

    ROUTING_SYSTEM_PROMPT = """You are a travel planning coordinator for a multi-section itinerary system.

Your job is to analyze the user's request and determine which section(s) of the itinerary need attention.

SECTIONS:
- overview: Trip dates, destination, summary, budget totals, highlights
- flights: Flight search, selection, booking details (outbound and return)
- accommodations: Hotels, stays, nightly lodging arrangements
- activities: Day-by-day activities, excursions, and experiences
- logistics: Practical tips, transportation between places, packing, visa info

CLASSIFICATION RULES:
1. "Find flights" / "book flights" / "change flights" -> flights
2. "Find a hotel" / "cheaper accommodation" / "where to stay" -> accommodations
3. "What to do" / "activities" / "kitesurfing" / "add rest day" -> activities
4. "How to get there" / "transportation" / "visa" / "packing" -> logistics
5. "Change dates" / "update summary" / "trip overview" -> overview

If the request affects multiple sections:
- Set primary_section to the main one
- List others in secondary_sections

If the request is ambiguous (confidence < 0.7):
- Set clarification_needed with a question to ask the user

Use the classify_intent tool to route the request.
"""

    def __init__(self):
        self.client = AsyncAnthropic()
        self.agents = {
            name: AgentClass() for name, AgentClass in self.SECTION_AGENTS.items()
        }

    async def classify_request(
        self,
        user_message: str,
        itinerary: SectionedItinerary,
    ) -> IntentClassification:
        """Determine which sections are affected by the user's request."""

        # Build context for classification
        context = f"""Current itinerary:
Destination: {itinerary.overview.destination}
Dates: {itinerary.overview.start_date} to {itinerary.overview.end_date}
Travelers: {itinerary.overview.num_travelers}

User request: {user_message}

Classify this request."""

        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=self.ROUTING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
            tools=[INTENT_CLASSIFICATION_TOOL],
            tool_choice={"type": "tool", "name": "classify_intent"},
        )

        # Extract classification from tool use
        for block in response.content:
            if block.type == "tool_use" and block.name == "classify_intent":
                return IntentClassification(**block.input)

        # Fallback if no tool use (shouldn't happen with tool_choice)
        return IntentClassification(
            primary_section="overview",
            action_type="clarify",
            confidence=0.3,
            clarification_needed="I couldn't understand which part of your itinerary you want to modify. Could you clarify?",
        )

    async def dispatch_to_agent(
        self,
        section: str,
        user_message: str,
        itinerary: SectionedItinerary,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SectionResult:
        """Dispatch request to a specialized agent."""

        if section not in self.agents:
            raise ValueError(f"Unknown section: {section}")

        agent = self.agents[section]

        # Build handoff
        current_state = getattr(itinerary, section).model_dump()

        # Get related section data based on section type
        related_sections = self._get_related_sections(section, itinerary)

        # Build constraints from other sections
        constraints = self._build_constraints(section, itinerary)

        handoff = SectionHandoff(
            section_type=section,
            current_state=current_state,
            user_request=user_message,
            constraints=constraints,
            related_sections=related_sections,
            preferences=preferences,
        )

        # Process with agent
        messages = [{"role": "user", "content": user_message}]
        result = None

        async for event in agent.process(handoff, messages):
            if event["type"] == "done":
                result = SectionResult(**event["result"])

        return result

    def _get_related_sections(
        self,
        section: str,
        itinerary: SectionedItinerary,
    ) -> Dict[str, Any]:
        """Get relevant data from other sections."""
        related = {}

        if section == "flights":
            # Flights needs to know dates from overview
            related["overview"] = {
                "start_date": itinerary.overview.start_date,
                "end_date": itinerary.overview.end_date,
                "destination": itinerary.overview.destination,
            }
        elif section == "accommodations":
            # Accommodations needs activity locations
            related["activities"] = {
                "locations": [d.location for d in itinerary.activities.days],
            }
            related["overview"] = {
                "start_date": itinerary.overview.start_date,
                "end_date": itinerary.overview.end_date,
            }
        elif section == "activities":
            # Activities needs flight arrival/departure times
            related["flights"] = {
                "has_outbound": bool(itinerary.flights.outbound_flights),
                "has_return": bool(itinerary.flights.return_flights),
            }
            related["accommodations"] = {
                "locations": [n.area for n in itinerary.accommodations.nights],
            }
        elif section == "logistics":
            # Logistics needs everything
            related["overview"] = itinerary.overview.model_dump()
            related["flights"] = {
                "has_flights": bool(itinerary.flights.outbound_flights)
            }

        return related

    def _build_constraints(
        self,
        section: str,
        itinerary: SectionedItinerary,
    ) -> List[str]:
        """Build constraints from other sections."""
        constraints = []

        if section == "flights":
            constraints.append(
                f"Trip dates: {itinerary.overview.start_date} to {itinerary.overview.end_date}"
            )
            constraints.append(f"Travelers: {itinerary.overview.num_travelers}")

        elif section == "accommodations":
            constraints.append(
                f"Trip dates: {itinerary.overview.start_date} to {itinerary.overview.end_date}"
            )
            if itinerary.activities.days:
                locations = set(d.location for d in itinerary.activities.days)
                constraints.append(f"Activity locations: {', '.join(locations)}")

        elif section == "activities":
            constraints.append(
                f"Trip dates: {itinerary.overview.start_date} to {itinerary.overview.end_date}"
            )
            # Add flight constraints if they exist
            if itinerary.flights.selected_outbound_id:
                constraints.append(
                    "Outbound flight is booked - first day starts after arrival"
                )
            if itinerary.flights.selected_return_id:
                constraints.append(
                    "Return flight is booked - last day ends before departure"
                )

        return constraints

    def validate_consistency(
        self,
        itinerary: SectionedItinerary,
        updated_sections: List[str],
    ) -> ValidationResult:
        """Validate cross-section consistency after updates."""
        issues = []

        # Check date alignment
        if "flights" in updated_sections or "overview" in updated_sections:
            # Verify flights match itinerary dates
            # (simplified check - real implementation would check actual flight dates)
            pass

        # Check activity days match date range
        if "activities" in updated_sections or "overview" in updated_sections:
            from datetime import datetime

            try:
                start = datetime.strptime(itinerary.overview.start_date, "%Y-%m-%d")
                end = datetime.strptime(itinerary.overview.end_date, "%Y-%m-%d")
                expected_days = (end - start).days + 1
                actual_days = len(itinerary.activities.days)

                if actual_days != expected_days:
                    issues.append(
                        ConsistencyIssue(
                            issue_type="day_count_mismatch",
                            description=f"Activities has {actual_days} days but trip is {expected_days} days",
                            affected_sections=["activities", "overview"],
                            suggested_fix="Adjust activities to match trip dates",
                            severity="warning",
                        )
                    )
            except ValueError:
                pass

        # Check accommodation coverage
        if "accommodations" in updated_sections:
            from datetime import datetime

            try:
                start = datetime.strptime(itinerary.overview.start_date, "%Y-%m-%d")
                end = datetime.strptime(itinerary.overview.end_date, "%Y-%m-%d")
                nights_needed = (end - start).days
                nights_booked = len(itinerary.accommodations.nights)

                if nights_booked < nights_needed:
                    issues.append(
                        ConsistencyIssue(
                            issue_type="accommodation_gap",
                            description=f"Only {nights_booked} nights booked but need {nights_needed}",
                            affected_sections=["accommodations"],
                            suggested_fix="Add accommodation for missing nights",
                            severity="warning",
                        )
                    )
            except ValueError:
                pass

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
        )

    async def process_request(
        self,
        user_message: str,
        itinerary: SectionedItinerary,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user request through the orchestration pipeline.

        Yields events for streaming:
        - {"type": "classification", "data": IntentClassification}
        - {"type": "clarification_needed", "question": str}
        - {"type": "agent_start", "section": str}
        - {"type": "agent_text", "section": str, "content": str}
        - {"type": "agent_done", "section": str, "result": SectionResult}
        - {"type": "validation", "result": ValidationResult}
        - {"type": "done", "result": OrchestratorResult}
        """

        # Step 1: Classify intent
        classification = await self.classify_request(user_message, itinerary)
        yield {"type": "classification", "data": classification.model_dump()}

        # Check if clarification needed
        if classification.confidence < 0.7 and classification.clarification_needed:
            yield {
                "type": "clarification_needed",
                "question": classification.clarification_needed,
            }
            return

        # Step 2: Dispatch to agents
        sections_to_update = [
            classification.primary_section
        ] + classification.secondary_sections
        agent_results: List[SectionResult] = []
        updated_itinerary = itinerary.model_copy(deep=True)

        # Check if sections can run in parallel (no dependencies)
        can_parallelize = self._can_parallelize(sections_to_update)

        if can_parallelize and len(sections_to_update) > 1:
            # Run agents in parallel
            yield {"type": "parallel_start", "sections": sections_to_update}
            tasks = [
                self.dispatch_to_agent(
                    section, user_message, updated_itinerary, preferences
                )
                for section in sections_to_update
            ]
            results = await asyncio.gather(*tasks)
            for section, result in zip(sections_to_update, results):
                yield {
                    "type": "agent_done",
                    "section": section,
                    "result": result.model_dump(),
                }
                agent_results.append(result)
                # Apply update
                setattr(
                    updated_itinerary,
                    section,
                    type(getattr(updated_itinerary, section))(**result.updated_state),
                )
        else:
            # Run agents sequentially
            for section in sections_to_update:
                yield {"type": "agent_start", "section": section}
                result = await self.dispatch_to_agent(
                    section, user_message, updated_itinerary, preferences
                )
                yield {
                    "type": "agent_done",
                    "section": section,
                    "result": result.model_dump(),
                }
                agent_results.append(result)
                # Apply update
                setattr(
                    updated_itinerary,
                    section,
                    type(getattr(updated_itinerary, section))(**result.updated_state),
                )

        # Step 3: Handle cross-section impacts
        all_impacts = []
        for result in agent_results:
            all_impacts.extend(result.cross_section_impacts)

        if all_impacts:
            yield {
                "type": "cross_section_impacts",
                "impacts": [i.model_dump() for i in all_impacts],
            }
            # TODO: Propagate impacts to affected sections

        # Step 4: Validate consistency
        validation = self.validate_consistency(updated_itinerary, sections_to_update)
        yield {"type": "validation", "result": validation.model_dump()}

        # Step 5: Final result
        final_result = OrchestratorResult(
            itinerary=updated_itinerary,
            sections_updated=sections_to_update,
            agent_responses=agent_results,
            validation_result=validation,
        )
        yield {"type": "done", "result": final_result.model_dump()}

    def _can_parallelize(self, sections: List[str]) -> bool:
        """Check if sections can run in parallel (no dependencies)."""
        # Define dependencies: section -> depends on
        dependencies = {
            "flights": [],
            "accommodations": ["activities"],  # May need activity locations
            "activities": ["flights"],  # May need arrival times
            "logistics": ["flights", "accommodations", "activities"],
        }

        for section in sections:
            for dep in dependencies.get(section, []):
                if dep in sections:
                    return False
        return True

    def _build_initial_shell(
        self,
        destination: str,
        start_date: str,
        end_date: str,
        num_travelers: int,
    ) -> SectionedItinerary:
        """Build an empty itinerary shell for initial generation."""
        now = datetime.utcnow().isoformat()
        return SectionedItinerary(
            id=str(uuid.uuid4()),
            overview=OverviewSection(
                destination=destination,
                start_date=start_date,
                end_date=end_date,
                num_travelers=num_travelers,
                title="",  # Filled by LogisticsAgent
                summary="",  # Filled by LogisticsAgent
                highlights=[],  # Filled by LogisticsAgent
                total_budget_estimate="TBD",
            ),
            flights=FlightsSection(),  # Empty - user requests via refinement
            accommodations=AccommodationsSection(),  # Empty - user requests via refinement
            activities=ActivitiesSection(),  # Filled by ActivitiesAgent
            logistics=LogisticsSection(),  # Filled by LogisticsAgent
            version=1,
            created_at=now,
            updated_at=now,
        )

    def validate_consistency_for_generation(
        self,
        itinerary: SectionedItinerary,
    ) -> ValidationResult:
        """Validate cross-section consistency for initial generation.

        More lenient than full validation - allows empty sections.
        """
        issues = []

        # Check activity days match date range if activities exist
        if itinerary.activities.days:
            try:
                start = datetime.strptime(itinerary.overview.start_date, "%Y-%m-%d")
                end = datetime.strptime(itinerary.overview.end_date, "%Y-%m-%d")
                expected_days = (end - start).days + 1
                actual_days = len(itinerary.activities.days)

                if actual_days != expected_days:
                    issues.append(
                        ConsistencyIssue(
                            issue_type="day_count_mismatch",
                            description=f"Activities has {actual_days} days but trip is {expected_days} days",
                            affected_sections=["activities", "overview"],
                            suggested_fix="Adjust activities to match trip dates",
                            severity="warning",
                        )
                    )
            except ValueError:
                pass

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
        )

    async def generate_initial_itinerary(
        self,
        destination: str,
        start_date: str,
        end_date: str,
        num_travelers: int,
        user_request: str,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate a new sectioned itinerary from scratch.

        Uses ActivitiesAgent for day-by-day planning and LogisticsAgent for
        overview/tips. Flights and accommodations start empty for user to
        request via refinement.

        Yields streaming events:
        - {"type": "generation_start", "destination": str}
        - {"type": "agent_start", "section": str}
        - {"type": "agent_done", "section": str, "result": dict}
        - {"type": "validation", "result": dict}
        - {"type": "done", "itinerary": dict}
        """
        # Create empty shell
        itinerary = self._build_initial_shell(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            num_travelers=num_travelers,
        )

        yield {"type": "generation_start", "destination": destination}

        # Calculate trip duration for prompt
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        num_days = (end_dt - start_dt).days + 1

        # Run both agents IN PARALLEL for faster generation
        yield {"type": "agent_start", "section": "activities"}
        yield {"type": "agent_start", "section": "logistics"}

        # Prepare both agent tasks
        # preferences is already a dict (from function signature), no need for model_dump
        activities_task = self.dispatch_to_agent(
            "activities",
            f"Plan {num_days} days of activities for {destination} based on: {user_request}",
            itinerary,
            preferences,
        )

        logistics_task = self.dispatch_to_agent(
            "logistics",
            f"Create logistics tips for {destination}: transportation, packing, visa requirements, health/safety, and important caveats. User request: {user_request}",
            itinerary,
            preferences,
        )

        # Execute both agents in parallel
        import asyncio
        activities_result, logistics_result = await asyncio.gather(
            activities_task,
            logistics_task,
        )

        # Update itinerary with both results
        if activities_result.updated_state:
            itinerary.activities = ActivitiesSection(**activities_result.updated_state)
            itinerary.updated_at = datetime.utcnow().isoformat()

        yield {
            "type": "agent_done",
            "section": "activities",
            "result": activities_result.model_dump(),
        }

        if logistics_result.updated_state:
            itinerary.logistics = LogisticsSection(**logistics_result.updated_state)
            itinerary.updated_at = datetime.utcnow().isoformat()

        yield {
            "type": "agent_done",
            "section": "logistics",
            "result": logistics_result.model_dump(),
        }

        # Generate overview based on completed activities
        itinerary.overview.title = f"{num_days}-Day {destination} Adventure"

        # Create summary from activities (activities.days is a list of dicts, not Pydantic models)
        activity_count = 0
        if itinerary.activities.days:
            for day in itinerary.activities.days:
                if isinstance(day, dict):
                    activity_count += len(day.get("activities", []))
                else:
                    # It's a Pydantic model
                    activity_count += len(getattr(day, "activities", []))

        itinerary.overview.summary = (
            f"A {num_days}-day trip to {destination} with {activity_count} curated activities. "
            f"This itinerary combines cultural experiences, local cuisine, and adventure."
        )

        # Create highlights from first few activities
        highlights = []
        if itinerary.activities.days:
            for day in itinerary.activities.days[:3]:  # First 3 days
                if isinstance(day, dict):
                    day_activities = day.get("activities", [])
                    if day_activities:
                        highlights.append(day_activities[0].get("name", ""))
                else:
                    # Pydantic model
                    day_activities = getattr(day, "activities", [])
                    if day_activities:
                        highlights.append(day_activities[0].name if hasattr(day_activities[0], "name") else "")

        if highlights:
            itinerary.overview.highlights = highlights[:3]  # Max 3 highlights

        # Step 3: Validate (lenient for generation)
        validation = self.validate_consistency_for_generation(itinerary)
        yield {"type": "validation", "result": validation.model_dump()}

        # Step 4: Final result
        yield {"type": "done", "itinerary": itinerary.model_dump()}


__all__ = [
    "ItineraryOrchestrator",
    "IntentClassification",
    "ConsistencyIssue",
    "ValidationResult",
    "OrchestratorResult",
    "INTENT_CLASSIFICATION_TOOL",
    "generate_initial_itinerary",
]
