from fastapi import APIRouter
from sqlmodel import select

from app.database import SessionDep
from app.models.user_preferences import UserPreferences
from app.schemas.preferences import PreferencesData

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesData)
def get_preferences(session: SessionDep) -> PreferencesData:
    """Retrieve user preferences, creating defaults if none exist."""
    prefs = session.exec(select(UserPreferences)).first()
    if prefs is None:
        prefs = UserPreferences(data=PreferencesData().model_dump())
        session.add(prefs)
        session.commit()
        session.refresh(prefs)
    return prefs.get_preferences()


@router.put("", response_model=PreferencesData)
def update_preferences(
    preferences: PreferencesData, session: SessionDep
) -> PreferencesData:
    """Update user preferences, creating the record if it doesn't exist."""
    prefs = session.exec(select(UserPreferences)).first()
    if prefs is None:
        prefs = UserPreferences()
        session.add(prefs)
    prefs.set_preferences(preferences)
    session.commit()
    session.refresh(prefs)
    return prefs.get_preferences()
