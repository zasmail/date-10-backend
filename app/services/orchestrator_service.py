"""Orchestrator service for multi-section itinerary updates."""

from typing import Any, AsyncGenerator, Dict, List, Optional

from app.agents.orchestrator import ItineraryOrchestrator, OrchestratorResult
from app.schemas.itinerary_sections import SectionedItinerary
from app.schemas.preferences import PreferencesData


# Global orchestrator instance
_orchestrator: Optional[ItineraryOrchestrator] = None


def get_orchestrator() -> ItineraryOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ItineraryOrchestrator()
    return _orchestrator


async def orchestrate_section_update(
    user_message: str,
    itinerary: SectionedItinerary,
    preferences: Optional[PreferencesData] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Orchestrate a section update request.

    This is the main entry point for multi-section updates.
    It analyzes the user request, dispatches to appropriate agents,
    and returns streaming events.

    Args:
        user_message: The user's natural language request
        itinerary: Current sectioned itinerary state
        preferences: Optional user preferences for context

    Yields:
        Event dicts for streaming to frontend
    """
    orchestrator = get_orchestrator()

    prefs_dict = preferences.model_dump() if preferences else None

    async for event in orchestrator.process_request(
        user_message=user_message,
        itinerary=itinerary,
        preferences=prefs_dict,
    ):
        yield event


async def classify_user_intent(
    user_message: str,
    itinerary: SectionedItinerary,
) -> Dict[str, Any]:
    """
    Classify user intent without executing updates.

    Useful for UI to show which sections will be affected.
    """
    orchestrator = get_orchestrator()
    classification = await orchestrator.classify_request(user_message, itinerary)
    return classification.model_dump()


def validate_itinerary_consistency(
    itinerary: SectionedItinerary,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Validate itinerary consistency.

    Args:
        itinerary: The itinerary to validate
        sections: Optional list of sections to check (defaults to all)

    Returns:
        Validation result with any issues found
    """
    orchestrator = get_orchestrator()
    sections_to_check = sections or [
        "flights",
        "accommodations",
        "activities",
        "logistics",
    ]
    result = orchestrator.validate_consistency(itinerary, sections_to_check)
    return result.model_dump()


async def orchestrate_initial_generation(
    destination: str,
    start_date: str,
    end_date: str,
    num_travelers: int,
    user_request: str,
    preferences: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generate a new sectioned itinerary via orchestrator.

    Yields streaming events for SSE:
    - generation_start: Starting generation
    - agent_start: Agent beginning work on section
    - agent_done: Agent completed section
    - validation: Consistency check
    - done: Final itinerary

    Args:
        destination: Trip destination
        start_date: Trip start date (YYYY-MM-DD)
        end_date: Trip end date (YYYY-MM-DD)
        num_travelers: Number of travelers
        user_request: User's natural language request describing trip goals
        preferences: Optional user preferences for context

    Yields:
        Event dicts for streaming to frontend
    """
    orchestrator = get_orchestrator()
    async for event in orchestrator.generate_initial_itinerary(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        num_travelers=num_travelers,
        user_request=user_request,
        preferences=preferences,
    ):
        yield event


__all__ = [
    "get_orchestrator",
    "orchestrate_section_update",
    "classify_user_intent",
    "validate_itinerary_consistency",
    "orchestrate_initial_generation",
]
