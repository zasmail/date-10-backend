from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
import uuid

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    pass


class Conversation(SQLModel, table=True):
    """A chat conversation with Claude for travel planning."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(default="default", index=True)  # Hardcode "default" for now (no auth)
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    messages: List["Message"] = Relationship(back_populates="conversation")


class Message(SQLModel, table=True):
    """A single message in a conversation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id", index=True)
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    conversation: Optional[Conversation] = Relationship(back_populates="messages")
