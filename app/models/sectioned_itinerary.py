"""Sectioned Itinerary SQLModel for database persistence.

This module provides the database model for storing sectioned itineraries
and a migration utility for converting legacy ItineraryProposal data.
"""

from datetime import datetime
from typing import Optional
import uuid
import json

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text

from app.schemas.itinerary_sections import (
    SectionedItinerary,
    OverviewSection,
    FlightsSection,
    AccommodationsSection,
    AccommodationNight,
    ActivitiesSection,
    ActivityDay,
    ActivityItem,
    LogisticsSection,
)


class SectionedItineraryModel(SQLModel, table=True):
    """Stored sectioned itinerary with sections as JSON.

    This model stores the complete sectioned itinerary in a JSON column,
    with denormalized fields for quick filtering and display.
    """

    __tablename__ = "sectioned_itinerary"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    conversation_id: Optional[str] = Field(default=None, index=True)
    user_id: str = Field(default="default", index=True)

    # Denormalized fields for quick filtering/display
    destination: str
    start_date: str
    end_date: str
    num_travelers: int = Field(default=1)
    title: str = Field(default="")

    # Section data stored as JSON
    sections_json: str = Field(sa_column=Column(Text))

    # Tracking
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Legacy link (for migration)
    legacy_itinerary_id: Optional[str] = Field(default=None)

    @property
    def sections(self) -> SectionedItinerary:
        """Parse sections from JSON."""
        data = json.loads(self.sections_json)
        return SectionedItinerary(**data)

    @sections.setter
    def sections(self, value: SectionedItinerary):
        """Serialize sections to JSON."""
        self.sections_json = value.model_dump_json()

    def get_section(self, section_name: str):
        """Get a specific section by name.

        Args:
            section_name: One of 'overview', 'flights', 'accommodations',
                          'activities', or 'logistics'

        Returns:
            The requested section object, or None if not found
        """
        sections = self.sections
        return getattr(sections, section_name, None)

    def update_section(self, section_name: str, section_data: dict) -> None:
        """Update a single section and bump version.

        Args:
            section_name: The section to update
            section_data: New data for the section

        This method allows specialized agents to update individual sections
        without affecting other sections.
        """
        sections_dict = json.loads(self.sections_json)
        sections_dict[section_name] = section_data
        sections_dict["updated_at"] = datetime.utcnow().isoformat()
        self.sections_json = json.dumps(sections_dict)
        self.version += 1
        self.updated_at = datetime.utcnow()

    @classmethod
    def from_sections(
        cls,
        sections: SectionedItinerary,
        conversation_id: Optional[str] = None,
        user_id: str = "default",
    ) -> "SectionedItineraryModel":
        """Create a model instance from a SectionedItinerary schema.

        Args:
            sections: The sectioned itinerary data
            conversation_id: Optional conversation ID to link
            user_id: User ID (defaults to 'default')

        Returns:
            A new SectionedItineraryModel instance
        """
        return cls(
            id=sections.id,
            conversation_id=conversation_id,
            user_id=user_id,
            destination=sections.overview.destination,
            start_date=sections.overview.start_date,
            end_date=sections.overview.end_date,
            num_travelers=sections.overview.num_travelers,
            title=sections.overview.title,
            sections_json=sections.model_dump_json(),
            version=sections.version,
        )


def migrate_proposal_to_sections(
    proposal: dict,
    destination: str,
    start_date: str,
    end_date: str,
    num_travelers: int = 1,
) -> SectionedItinerary:
    """Convert monolithic ItineraryProposal to SectionedItinerary.

    This utility helps migrate existing itinerary data from the legacy
    ItineraryProposal format to the new sectioned format.

    Args:
        proposal: Legacy proposal dict with 'title', 'summary', 'days', etc.
        destination: Trip destination
        start_date: Trip start date (YYYY-MM-DD)
        end_date: Trip end date (YYYY-MM-DD)
        num_travelers: Number of travelers

    Returns:
        A new SectionedItinerary with data extracted from the proposal
    """
    # Extract overview
    overview = OverviewSection(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        num_travelers=num_travelers,
        title=proposal.get("title", ""),
        summary=proposal.get("summary", ""),
        highlights=proposal.get("highlights", []),
        total_budget_estimate=proposal.get("total_budget_estimate", "TBD"),
    )

    # Extract accommodations and activities from days
    accommodation_nights = []
    activity_days = []

    for day in proposal.get("days", []):
        # Build activity items
        activities = []
        for a in day.get("activities", []):
            activities.append(
                ActivityItem(
                    time=a.get("time", ""),
                    name=a.get("name", ""),
                    description=a.get("description", ""),
                    duration=a.get("duration", ""),
                    location=a.get("location"),
                    cost_estimate=a.get("cost_estimate"),
                    booking_required=a.get("booking_required", False),
                    operator=a.get("operator"),
                )
            )

        # Build activity day
        activity_days.append(
            ActivityDay(
                day_number=day["day_number"],
                date=day["date"],
                title=day["title"],
                location=day["location"],
                activities=activities,
                notes=day.get("notes", ""),
            )
        )

        # Extract accommodation if present
        if day.get("accommodation"):
            acc = day["accommodation"]
            accommodation_nights.append(
                AccommodationNight(
                    date=day["date"],
                    name=acc.get("name", ""),
                    area=acc.get("area", ""),
                    style=acc.get("style", ""),
                    price_range=acc.get("price_range", ""),
                    notes=acc.get("notes", ""),
                    booking_link=acc.get("booking_link"),
                )
            )

    # Extract logistics from caveats
    logistics = LogisticsSection(
        caveats=proposal.get("caveats", []),
    )

    return SectionedItinerary(
        id=proposal.get("id", str(uuid.uuid4())),
        overview=overview,
        flights=FlightsSection(),  # Empty - to be populated by flight agent
        accommodations=AccommodationsSection(nights=accommodation_nights),
        activities=ActivitiesSection(days=activity_days),
        logistics=logistics,
        version=1,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )


__all__ = [
    "SectionedItineraryModel",
    "migrate_proposal_to_sections",
]
