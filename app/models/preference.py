from typing import Optional

from sqlmodel import Field, SQLModel


class PreferenceBase(SQLModel):
    key: str = Field(index=True)
    value: str
    category: Optional[str] = None


class Preference(PreferenceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class PreferenceCreate(PreferenceBase):
    pass


class PreferencePublic(PreferenceBase):
    id: int
