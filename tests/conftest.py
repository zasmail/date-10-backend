"""Pytest fixtures for Wanderlust tests."""

import pytest

from app.knowledge.destination_knowledge import load_knowledge_base
from app.knowledge.schemas import DestinationKnowledgeBase
from app.schemas.preferences import (
    ActivityPreferences,
    DestinationPreferences,
    PreferencesData,
)


@pytest.fixture
def sample_preferences() -> PreferencesData:
    """Sample preferences for testing prompt generation."""
    return PreferencesData(
        activities=ActivityPreferences(preferred=["kitesurfing", "surfing"]),
        destinations=DestinationPreferences(
            bucket_list=["Tarifa", "Cape Town"],
            visited=["Bali"],
        ),
    )


@pytest.fixture
def knowledge_base() -> DestinationKnowledgeBase:
    """Load the real destination knowledge base for testing."""
    return load_knowledge_base()
