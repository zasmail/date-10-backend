from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str
    conversation_id: Optional[str] = None  # If None, creates new conversation


class MessageSchema(BaseModel):
    """Schema for message in API responses."""

    id: str
    role: str
    content: str
    created_at: str


class ConversationSchema(BaseModel):
    """Schema for conversation in API responses."""

    id: str
    title: Optional[str]
    messages: List[MessageSchema]
