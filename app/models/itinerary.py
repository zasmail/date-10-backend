"""Itinerary SQLModel for database persistence."""

from datetime import datetime
from typing import Optional
import uuid
import json

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text


class Itinerary(SQLModel, table=True):
    """Stored itinerary with proposals as JSON."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    conversation_id: Optional[str] = Field(default=None, foreign_key="conversation.id", index=True)
    user_id: str = Field(default="default", index=True)
    destination: str
    start_date: str
    end_date: str
    num_travelers: int = Field(default=1)
    proposals_json: str = Field(sa_column=Column(Text))  # JSON string
    selected_proposal_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def proposals(self):
        """Parse proposals from JSON."""
        from app.schemas.itinerary import ItineraryProposal

        data = json.loads(self.proposals_json)
        return [ItineraryProposal(**p) for p in data]

    @proposals.setter
    def proposals(self, value):
        """Serialize proposals to JSON."""
        self.proposals_json = json.dumps([p.model_dump() for p in value])
