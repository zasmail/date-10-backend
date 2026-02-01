"""Version history service for itinerary snapshots and rollback."""

from typing import List, Optional

from sqlmodel import Session, select, func

from app.models.itinerary import Itinerary
from app.models.itinerary_version import ItineraryVersion


def create_version(
    session: Session,
    itinerary: Itinerary,
    change_description: str = "",
) -> ItineraryVersion:
    """
    Create a new version snapshot of the current itinerary state.

    Args:
        session: Database session
        itinerary: The itinerary to snapshot
        change_description: Description of what changed

    Returns:
        The created ItineraryVersion
    """
    # Get the next version number for this itinerary
    max_version = session.exec(
        select(func.max(ItineraryVersion.version_number)).where(
            ItineraryVersion.itinerary_id == itinerary.id
        )
    ).one()

    next_version = (max_version or 0) + 1

    # Create the version snapshot
    version = ItineraryVersion(
        itinerary_id=itinerary.id,
        version_number=next_version,
        destination=itinerary.destination,
        start_date=itinerary.start_date,
        end_date=itinerary.end_date,
        num_travelers=itinerary.num_travelers,
        proposals_json=itinerary.proposals_json,
        selected_proposal_id=itinerary.selected_proposal_id,
        change_description=change_description,
    )

    session.add(version)
    session.commit()
    session.refresh(version)

    return version


def get_versions(
    session: Session,
    itinerary_id: str,
) -> List[ItineraryVersion]:
    """
    Get all versions for an itinerary, ordered by version number descending.

    Args:
        session: Database session
        itinerary_id: ID of the itinerary

    Returns:
        List of ItineraryVersion objects, newest first
    """
    versions = session.exec(
        select(ItineraryVersion)
        .where(ItineraryVersion.itinerary_id == itinerary_id)
        .order_by(ItineraryVersion.version_number.desc())
    ).all()

    return list(versions)


def get_version(
    session: Session,
    version_id: str,
) -> Optional[ItineraryVersion]:
    """
    Get a specific version by its ID.

    Args:
        session: Database session
        version_id: ID of the version

    Returns:
        ItineraryVersion or None if not found
    """
    return session.get(ItineraryVersion, version_id)


def rollback_to_version(
    session: Session,
    itinerary: Itinerary,
    version: ItineraryVersion,
) -> Itinerary:
    """
    Restore an itinerary to a previous version state.

    This creates a new version (capturing the current state before rollback),
    then restores the itinerary fields from the target version.

    Args:
        session: Database session
        itinerary: The itinerary to restore
        version: The version to restore to

    Returns:
        The updated Itinerary
    """
    # First, create a version of current state before rollback
    create_version(
        session,
        itinerary,
        change_description=f"Before rollback to version {version.version_number}",
    )

    # Restore fields from the target version
    itinerary.destination = version.destination
    itinerary.start_date = version.start_date
    itinerary.end_date = version.end_date
    itinerary.num_travelers = version.num_travelers
    itinerary.proposals_json = version.proposals_json
    itinerary.selected_proposal_id = version.selected_proposal_id

    session.add(itinerary)
    session.commit()
    session.refresh(itinerary)

    # Create a version after rollback
    create_version(
        session,
        itinerary,
        change_description=f"Rolled back to version {version.version_number}",
    )

    return itinerary
