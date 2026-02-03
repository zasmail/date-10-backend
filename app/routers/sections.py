"""Section-level refinement API endpoints."""

import json
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from app.database import get_session, engine
from app.models import UserPreferences
from app.models.sectioned_itinerary import SectionedItineraryModel, migrate_proposal_to_sections
from app.schemas.itinerary_sections import SectionedItinerary
from app.schemas.preferences import PreferencesData
from app.services.orchestrator_service import (
    orchestrate_section_update,
    classify_user_intent,
    validate_itinerary_consistency,
    orchestrate_initial_generation,
)


router = APIRouter(prefix="/sections", tags=["sections"])

# In-memory storage for generation tasks
generation_tasks: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Request/Response Models
# ============================================================================


class RefineSectionRequest(BaseModel):
    """Request to refine a section via natural language."""
    message: str  # e.g., "Find cheaper flight options" or "Add a rest day after day 3"
    target_section: Optional[str] = None  # Optional hint: flights, accommodations, activities, logistics


class ClassifyIntentRequest(BaseModel):
    """Request to classify intent without executing."""
    message: str


class ClassifyIntentResponse(BaseModel):
    """Response with intent classification."""
    primary_section: str
    secondary_sections: List[str]
    action_type: str
    confidence: float
    clarification_needed: Optional[str] = None


class ValidateRequest(BaseModel):
    """Request to validate consistency."""
    sections: Optional[List[str]] = None  # Which sections to validate (default: all)


class ValidateResponse(BaseModel):
    """Response with validation result."""
    is_valid: bool
    issues: List[dict]


class SectionedItineraryResponse(BaseModel):
    """Response model for sectioned itinerary."""
    id: str
    destination: str
    start_date: str
    end_date: str
    num_travelers: int
    title: str
    sections: dict  # Full sections data
    version: int
    created_at: datetime
    updated_at: datetime


class MigrateRequest(BaseModel):
    """Request to migrate a legacy itinerary."""
    legacy_itinerary_id: str
    proposal_id: Optional[str] = None  # Which proposal to migrate (default: selected or first)


class GenerateSectionedRequest(BaseModel):
    """Request to generate a new sectioned itinerary."""
    destination: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    num_travelers: int = 2
    message: str     # User request describing trip goals


class GenerationTaskResponse(BaseModel):
    """Response when starting generation task."""
    task_id: str
    status: str  # 'started'


class GenerationStatusResponse(BaseModel):
    """Response for polling generation status."""
    task_id: str
    status: str  # 'processing', 'completed', 'failed'
    progress: str  # Human-readable status message
    current_section: Optional[str] = None
    itinerary_id: Optional[str] = None
    itinerary: Optional[dict] = None
    error: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/{itinerary_id}", response_model=SectionedItineraryResponse)
async def get_sectioned_itinerary(
    itinerary_id: str,
    session: Session = Depends(get_session),
):
    """Get a sectioned itinerary by ID."""
    itinerary = session.get(SectionedItineraryModel, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Sectioned itinerary not found")

    return SectionedItineraryResponse(
        id=itinerary.id,
        destination=itinerary.destination,
        start_date=itinerary.start_date,
        end_date=itinerary.end_date,
        num_travelers=itinerary.num_travelers,
        title=itinerary.title,
        sections=json.loads(itinerary.sections_json),
        version=itinerary.version,
        created_at=itinerary.created_at,
        updated_at=itinerary.updated_at,
    )


@router.get("/{itinerary_id}/section/{section_name}")
async def get_section(
    itinerary_id: str,
    section_name: str,
    session: Session = Depends(get_session),
):
    """Get a specific section from an itinerary."""
    valid_sections = ["overview", "flights", "accommodations", "activities", "logistics"]
    if section_name not in valid_sections:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section. Must be one of: {valid_sections}"
        )

    itinerary = session.get(SectionedItineraryModel, itinerary_id)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    sections = json.loads(itinerary.sections_json)
    return {"section": section_name, "data": sections.get(section_name, {})}


@router.post("/{itinerary_id}/refine")
async def refine_section(
    itinerary_id: str,
    request: RefineSectionRequest,
    session: Session = Depends(get_session),
):
    """
    Refine itinerary section(s) via natural language.

    Returns Server-Sent Events (SSE) stream with:
    - classification: Which sections will be updated
    - agent_start/agent_done: Agent progress
    - validation: Consistency check results
    - done: Final updated itinerary
    """
    itinerary_model = session.get(SectionedItineraryModel, itinerary_id)
    if not itinerary_model:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    # Load user preferences
    user_prefs = session.exec(select(UserPreferences)).first()

    preferences = None
    if user_prefs:
        preferences = user_prefs.get_preferences()

    # Parse current itinerary
    itinerary = itinerary_model.sections

    async def event_generator():
        """Generate SSE events for streaming response."""
        updated_itinerary = None
        current_version = itinerary_model.version

        async for event in orchestrate_section_update(
            user_message=request.message,
            itinerary=itinerary,
            preferences=preferences,
        ):
            event_type = event.get("type", "unknown")

            if event_type == "classification":
                yield {"event": "classification", "data": json.dumps(event["data"])}

            elif event_type == "clarification_needed":
                yield {"event": "clarification", "data": json.dumps({"question": event["question"]})}

            elif event_type == "agent_start":
                yield {"event": "agent_start", "data": json.dumps({"section": event["section"]})}

            elif event_type == "agent_done":
                yield {"event": "agent_done", "data": json.dumps({
                    "section": event["section"],
                    "changes": event["result"].get("changes_made", []),
                })}

            elif event_type == "validation":
                yield {"event": "validation", "data": json.dumps(event["result"])}

            elif event_type == "cross_section_impacts":
                yield {"event": "impacts", "data": json.dumps(event["impacts"])}

            elif event_type == "done":
                result = event["result"]
                updated_itinerary = SectionedItinerary(**result["itinerary"])

                # Persist the updated itinerary
                with Session(engine) as save_session:
                    model = save_session.get(SectionedItineraryModel, itinerary_id)
                    if model:
                        model.sections = updated_itinerary
                        model.version += 1
                        model.updated_at = datetime.utcnow()
                        current_version = model.version
                        save_session.add(model)
                        save_session.commit()

                yield {"event": "done", "data": json.dumps({
                    "itinerary_id": itinerary_id,
                    "version": current_version,
                    "sections_updated": result["sections_updated"],
                })}

    return EventSourceResponse(event_generator())


@router.post("/{itinerary_id}/classify")
async def classify_intent(
    itinerary_id: str,
    request: ClassifyIntentRequest,
    session: Session = Depends(get_session),
) -> ClassifyIntentResponse:
    """
    Classify user intent without executing updates.

    Useful for UI to preview which sections will be affected.
    """
    itinerary_model = session.get(SectionedItineraryModel, itinerary_id)
    if not itinerary_model:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    itinerary = itinerary_model.sections
    result = await classify_user_intent(request.message, itinerary)

    return ClassifyIntentResponse(**result)


@router.post("/{itinerary_id}/validate")
async def validate_consistency(
    itinerary_id: str,
    request: ValidateRequest,
    session: Session = Depends(get_session),
) -> ValidateResponse:
    """
    Validate cross-section consistency.

    Returns any issues found (date mismatches, missing accommodations, etc.)
    """
    itinerary_model = session.get(SectionedItineraryModel, itinerary_id)
    if not itinerary_model:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    itinerary = itinerary_model.sections
    result = validate_itinerary_consistency(itinerary, request.sections)

    return ValidateResponse(**result)


@router.post("/migrate", response_model=SectionedItineraryResponse)
async def migrate_legacy_itinerary(
    request: MigrateRequest,
    session: Session = Depends(get_session),
):
    """
    Migrate a legacy monolithic itinerary to sectioned format.

    Takes an existing Itinerary and creates a new SectionedItineraryModel.
    """
    from app.models import Itinerary

    # Get legacy itinerary
    legacy = session.get(Itinerary, request.legacy_itinerary_id)
    if not legacy:
        raise HTTPException(status_code=404, detail="Legacy itinerary not found")

    # Get the proposal to migrate
    proposals = json.loads(legacy.proposals_json)
    if not proposals:
        raise HTTPException(status_code=400, detail="No proposals in legacy itinerary")

    proposal_to_migrate = None
    if request.proposal_id:
        proposal_to_migrate = next(
            (p for p in proposals if p.get("id") == request.proposal_id),
            None
        )
        if not proposal_to_migrate:
            raise HTTPException(status_code=400, detail="Proposal not found")
    elif legacy.selected_proposal_id:
        proposal_to_migrate = next(
            (p for p in proposals if p.get("id") == legacy.selected_proposal_id),
            None
        )
    if not proposal_to_migrate:
        proposal_to_migrate = proposals[0]

    # Migrate to sectioned format
    sectioned = migrate_proposal_to_sections(
        proposal=proposal_to_migrate,
        destination=legacy.destination,
        start_date=legacy.start_date,
        end_date=legacy.end_date,
        num_travelers=legacy.num_travelers,
    )

    # Create new model
    new_model = SectionedItineraryModel(
        conversation_id=legacy.conversation_id,
        user_id=legacy.user_id,
        destination=legacy.destination,
        start_date=legacy.start_date,
        end_date=legacy.end_date,
        num_travelers=legacy.num_travelers,
        title=proposal_to_migrate.get("title", ""),
        sections_json=sectioned.model_dump_json(),
        legacy_itinerary_id=legacy.id,
    )

    session.add(new_model)
    session.commit()
    session.refresh(new_model)

    return SectionedItineraryResponse(
        id=new_model.id,
        destination=new_model.destination,
        start_date=new_model.start_date,
        end_date=new_model.end_date,
        num_travelers=new_model.num_travelers,
        title=new_model.title,
        sections=json.loads(new_model.sections_json),
        version=new_model.version,
        created_at=new_model.created_at,
        updated_at=new_model.updated_at,
    )


@router.get("", response_model=List[SectionedItineraryResponse])
async def list_sectioned_itineraries(
    session: Session = Depends(get_session),
    limit: int = 20,
):
    """List all sectioned itineraries for the current user."""
    itineraries = session.exec(
        select(SectionedItineraryModel)
        .where(SectionedItineraryModel.user_id == "default")
        .order_by(SectionedItineraryModel.created_at.desc())
        .limit(limit)
    ).all()

    return [
        SectionedItineraryResponse(
            id=it.id,
            destination=it.destination,
            start_date=it.start_date,
            end_date=it.end_date,
            num_travelers=it.num_travelers,
            title=it.title,
            sections=json.loads(it.sections_json),
            version=it.version,
            created_at=it.created_at,
            updated_at=it.updated_at,
        )
        for it in itineraries
    ]


async def _run_generation_task(
    task_id: str,
    destination: str,
    start_date: str,
    end_date: str,
    num_travelers: int,
    message: str,
    preferences: Optional[PreferencesData],
):
    """Background task to run generation and update state."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"[Task {task_id}] Starting generation for {destination}")
        generation_tasks[task_id] = {
            "status": "processing",
            "progress": f"Starting {destination} itinerary...",
            "current_section": None,
            "itinerary_id": None,
            "itinerary": None,
            "error": None,
        }

        async for event in orchestrate_initial_generation(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            num_travelers=num_travelers,
            user_request=message,
            preferences=preferences.model_dump() if preferences else None,
        ):
            event_type = event.get("type", "unknown")
            logger.info(f"[Task {task_id}] Event: {event_type}")

            if event_type == "generation_start":
                generation_tasks[task_id]["progress"] = f"Starting {event.get('destination', destination)} itinerary..."
                logger.info(f"[Task {task_id}] Progress: {generation_tasks[task_id]['progress']}")

            elif event_type == "agent_start":
                section = event["section"]
                section_display = section.capitalize()
                generation_tasks[task_id]["progress"] = f"Planning {section_display}..."
                generation_tasks[task_id]["current_section"] = section
                logger.info(f"[Task {task_id}] Progress: {generation_tasks[task_id]['progress']}")

            elif event_type == "agent_done":
                section = event["section"]
                section_display = section.capitalize()
                generation_tasks[task_id]["progress"] = f"{section_display} complete"
                logger.info(f"[Task {task_id}] Progress: {generation_tasks[task_id]['progress']}")

            elif event_type == "validation":
                generation_tasks[task_id]["progress"] = "Validating consistency..."
                logger.info(f"[Task {task_id}] Progress: {generation_tasks[task_id]['progress']}")

            elif event_type == "done":
                # Persist the generated itinerary
                from app.schemas.itinerary_sections import SectionedItinerary
                itinerary = SectionedItinerary(**event["itinerary"])

                with Session(engine) as save_session:
                    model = SectionedItineraryModel(
                        user_id="default",
                        destination=destination,
                        start_date=start_date,
                        end_date=end_date,
                        num_travelers=num_travelers,
                        title=itinerary.overview.title or f"Trip to {destination}",
                        sections_json=itinerary.model_dump_json(),
                    )
                    save_session.add(model)
                    save_session.commit()
                    save_session.refresh(model)

                    generation_tasks[task_id].update({
                        "status": "completed",
                        "progress": "Complete",
                        "itinerary_id": model.id,
                        "itinerary": event["itinerary"],
                    })
                    logger.info(f"[Task {task_id}] COMPLETED - Itinerary ID: {model.id}")

    except Exception as e:
        logger.error(f"[Task {task_id}] FAILED: {str(e)}")
        generation_tasks[task_id].update({
            "status": "failed",
            "progress": "Generation failed",
            "error": str(e),
        })


@router.post("/generate", response_model=GenerationTaskResponse)
async def generate_sectioned_itinerary(
    request: GenerateSectionedRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Start generation of a new sectioned itinerary.

    Returns a task_id immediately. Poll /sections/generate/{task_id}/status to get progress.

    The generated itinerary has:
    - Populated activities section (day-by-day schedule)
    - Populated logistics section (tips, packing, transportation)
    - Empty flights section (user requests via refinement)
    - Empty accommodations section (user requests via refinement)
    """
    # Load user preferences
    user_prefs = session.exec(select(UserPreferences)).first()
    preferences = user_prefs.get_preferences() if user_prefs else None

    # Create task ID
    task_id = str(uuid.uuid4())

    # Start background task
    background_tasks.add_task(
        _run_generation_task,
        task_id,
        request.destination,
        request.start_date,
        request.end_date,
        request.num_travelers,
        request.message,
        preferences,
    )

    return GenerationTaskResponse(task_id=task_id, status="started")


@router.get("/generate/{task_id}/status", response_model=GenerationStatusResponse)
async def get_generation_status(task_id: str):
    """
    Poll the status of a generation task.

    Returns current progress and completion status.
    """
    if task_id not in generation_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task_data = generation_tasks[task_id]

    return GenerationStatusResponse(
        task_id=task_id,
        status=task_data["status"],
        progress=task_data["progress"],
        current_section=task_data.get("current_section"),
        itinerary_id=task_data.get("itinerary_id"),
        itinerary=task_data.get("itinerary"),
        error=task_data.get("error"),
    )


@router.get("/debug/tasks")
async def debug_tasks():
    """Debug endpoint to view all active generation tasks."""
    return {
        "total_tasks": len(generation_tasks),
        "tasks": {
            task_id: {
                "status": data["status"],
                "progress": data["progress"],
                "current_section": data.get("current_section"),
                "has_itinerary": data.get("itinerary") is not None,
            }
            for task_id, data in generation_tasks.items()
        }
    }
