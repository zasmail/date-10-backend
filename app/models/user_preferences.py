from typing import Any, Dict, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.schemas.preferences import PreferencesData


class UserPreferences(SQLModel, table=True):
    """User preferences stored as a JSON document in SQLite."""

    __tablename__ = "user_preferences"

    id: Optional[int] = Field(default=None, primary_key=True)
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    def get_preferences(self) -> PreferencesData:
        """Parse stored JSON data into PreferencesData model."""
        return PreferencesData.model_validate(self.data)

    def set_preferences(self, prefs: PreferencesData) -> None:
        """Store PreferencesData as JSON in the data field."""
        self.data = prefs.model_dump()
