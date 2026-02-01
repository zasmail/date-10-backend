"""ItineraryVersion SQLModel for version history tracking."""

from datetime import datetime
from typing import Optional
import uuid

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text


class ItineraryVersion(SQLModel, table=True):
    """Snapshot of an itinerary at a point in time for version history."""

    __tablename__ = "itinerary_version"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    itinerary_id: str = Field(foreign_key="itinerary.id", index=True)
    version_number: int = Field(default=1, index=True)

    # Snapshot of itinerary state
    destination: str
    start_date: str
    end_date: str
    num_travelers: int = Field(default=1)
    proposals_json: str = Field(sa_column=Column(Text))
    selected_proposal_id: Optional[str] = None

    # Version metadata
    change_description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
