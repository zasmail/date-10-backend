"""Activity and operator API endpoints."""

from fastapi import APIRouter

from app.knowledge.operator_knowledge import (
    load_operator_knowledge,
    get_operators_for_destination,
    get_operators_by_activity,
)
from app.knowledge.destination_knowledge import load_knowledge_base

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("/destinations")
async def list_activity_destinations():
    """List destinations with operator data."""
    kb = load_operator_knowledge()
    destinations = sorted(set(op.destination for op in kb.operators))
    return {"destinations": destinations, "total": len(destinations)}


@router.get("/operators/{destination}")
async def get_destination_operators(destination: str):
    """Get all operators for a destination."""
    operators = get_operators_for_destination(destination)
    return {
        "destination": destination,
        "operators": [op.model_dump() for op in operators],
        "count": len(operators),
    }


@router.get("/by-activity/{activity}")
async def get_activity_operators(activity: str):
    """Get operators offering a specific activity."""
    operators = get_operators_by_activity(activity)
    return {
        "activity": activity,
        "operators": [op.model_dump() for op in operators],
        "count": len(operators),
    }


@router.get("/seasonality/{destination}")
async def get_activity_seasonality(destination: str):
    """Get activity seasonality for a destination."""
    kb = load_knowledge_base()

    # Find the destination
    dest = None
    for d in kb.destinations:
        if d.name.lower() == destination.lower():
            dest = d
            break

    if not dest:
        return {"destination": destination, "activities": [], "found": False}

    activities = []
    for activity_name, activity_data in dest.activities.items():
        activities.append(
            {
                "activity": activity_name,
                "season_months": activity_data.season,
                "reliability": activity_data.reliability,
                "conditions": activity_data.conditions,
                "skill_level": activity_data.skill_level,
                "notes": activity_data.notes,
            }
        )

    return {"destination": destination, "activities": activities, "found": True}


@router.get("/available/{month}")
async def get_activities_by_month(month: int):
    """Get activities available in a specific month (1-12)."""
    if not 1 <= month <= 12:
        return {"error": "Month must be between 1 and 12"}

    kb = load_knowledge_base()

    available = []
    for dest in kb.destinations:
        dest_activities = []
        for activity_name, activity_data in dest.activities.items():
            if month in activity_data.season:
                dest_activities.append(
                    {
                        "activity": activity_name,
                        "reliability": activity_data.reliability,
                        "conditions": activity_data.conditions,
                    }
                )

        if dest_activities:
            available.append(
                {
                    "destination": dest.name,
                    "country": dest.country,
                    "activities": dest_activities,
                }
            )

    return {"month": month, "destinations": available, "count": len(available)}
