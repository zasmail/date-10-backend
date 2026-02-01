from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class TripBase(SQLModel):
    name: str = Field(index=True)
    destination: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class Trip(TripBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class TripCreate(TripBase):
    pass


class TripPublic(TripBase):
    id: int
