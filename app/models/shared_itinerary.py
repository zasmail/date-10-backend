"""SharedItinerary SQLModel for shareable read-only links."""

from datetime import datetime
from typing import Optional
import uuid
import secrets

from sqlmodel import Field, SQLModel


def generate_share_token() -> str:
    """Generate a URL-safe share token."""
    return secrets.token_urlsafe(16)


class SharedItinerary(SQLModel, table=True):
    """Shareable read-only itinerary link."""

    __tablename__ = "shared_itinerary"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    itinerary_id: str = Field(foreign_key="itinerary.id", index=True)
    share_token: str = Field(default_factory=generate_share_token, unique=True, index=True)
    title: Optional[str] = Field(default=None, description="Custom title for shared link")
    is_active: bool = Field(default=True, description="Whether link is still valid")
    view_count: int = Field(default=0, description="Number of times viewed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
