"""Tests for version service."""

import pytest
import json
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models import Itinerary
from app.models.itinerary_version import ItineraryVersion
from app.services.version_service import (
    create_version,
    get_versions,
    get_version,
    rollback_to_version,
)


@pytest.fixture(name="session")
def session_fixture():
    """Create a test database session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_itinerary(session: Session) -> Itinerary:
    """Create a sample itinerary for testing."""
    proposals = [
        {
            "id": "prop-1",
            "title": "Adventure",
            "summary": "Action-packed",
            "days": [],
            "total_budget_estimate": "$1500",
            "highlights": ["Surfing"],
            "caveats": ["Weather"],
        },
    ]

    itinerary = Itinerary(
        destination="Tarifa",
        start_date="2026-03-15",
        end_date="2026-03-20",
        num_travelers=2,
        proposals_json=json.dumps(proposals),
    )
    session.add(itinerary)
    session.commit()
    session.refresh(itinerary)
    return itinerary


class TestCreateVersion:
    """Tests for create_version function."""

    def test_creates_first_version(self, session: Session, sample_itinerary: Itinerary):
        """First version has version_number 1."""
        version = create_version(session, sample_itinerary, "Initial state")

        assert version.version_number == 1
        assert version.itinerary_id == sample_itinerary.id
        assert version.destination == "Tarifa"
        assert version.change_description == "Initial state"

    def test_increments_version_number(self, session: Session, sample_itinerary: Itinerary):
        """Each new version increments version_number."""
        v1 = create_version(session, sample_itinerary, "First")
        v2 = create_version(session, sample_itinerary, "Second")
        v3 = create_version(session, sample_itinerary, "Third")

        assert v1.version_number == 1
        assert v2.version_number == 2
        assert v3.version_number == 3

    def test_snapshots_current_state(self, session: Session, sample_itinerary: Itinerary):
        """Version captures current itinerary state."""
        # Create initial version
        create_version(session, sample_itinerary, "Before change")

        # Modify itinerary
        sample_itinerary.destination = "Cape Town"
        sample_itinerary.num_travelers = 4
        session.add(sample_itinerary)
        session.commit()

        # Create another version
        v2 = create_version(session, sample_itinerary, "After change")

        assert v2.destination == "Cape Town"
        assert v2.num_travelers == 4


class TestGetVersions:
    """Tests for get_versions function."""

    def test_returns_empty_list_when_no_versions(self, session: Session, sample_itinerary: Itinerary):
        """Returns empty list if no versions exist."""
        versions = get_versions(session, sample_itinerary.id)
        assert versions == []

    def test_returns_versions_ordered_by_version_number_desc(
        self, session: Session, sample_itinerary: Itinerary
    ):
        """Returns versions newest first."""
        create_version(session, sample_itinerary, "First")
        create_version(session, sample_itinerary, "Second")
        create_version(session, sample_itinerary, "Third")

        versions = get_versions(session, sample_itinerary.id)

        assert len(versions) == 3
        assert versions[0].version_number == 3
        assert versions[1].version_number == 2
        assert versions[2].version_number == 1

    def test_only_returns_versions_for_specified_itinerary(self, session: Session):
        """Only returns versions belonging to the specified itinerary."""
        # Create two itineraries
        it1 = Itinerary(
            destination="Tarifa",
            start_date="2026-03-15",
            end_date="2026-03-20",
            proposals_json="[]",
        )
        it2 = Itinerary(
            destination="Bali",
            start_date="2026-04-01",
            end_date="2026-04-10",
            proposals_json="[]",
        )
        session.add(it1)
        session.add(it2)
        session.commit()
        session.refresh(it1)
        session.refresh(it2)

        # Create versions for each
        create_version(session, it1, "Tarifa v1")
        create_version(session, it1, "Tarifa v2")
        create_version(session, it2, "Bali v1")

        versions_it1 = get_versions(session, it1.id)
        versions_it2 = get_versions(session, it2.id)

        assert len(versions_it1) == 2
        assert len(versions_it2) == 1
        assert all(v.destination == "Tarifa" for v in versions_it1)
        assert all(v.destination == "Bali" for v in versions_it2)


class TestGetVersion:
    """Tests for get_version function."""

    def test_returns_version_by_id(self, session: Session, sample_itinerary: Itinerary):
        """Returns version when it exists."""
        created = create_version(session, sample_itinerary, "Test")

        found = get_version(session, created.id)

        assert found is not None
        assert found.id == created.id
        assert found.change_description == "Test"

    def test_returns_none_for_nonexistent_id(self, session: Session):
        """Returns None for nonexistent version ID."""
        found = get_version(session, "nonexistent-id")
        assert found is None


class TestRollbackToVersion:
    """Tests for rollback_to_version function."""

    def test_restores_itinerary_state(self, session: Session, sample_itinerary: Itinerary):
        """Rollback restores itinerary fields from version."""
        # Save initial state
        v1 = create_version(session, sample_itinerary, "Initial")

        # Modify itinerary
        sample_itinerary.destination = "Cape Town"
        sample_itinerary.start_date = "2026-05-01"
        sample_itinerary.end_date = "2026-05-10"
        sample_itinerary.num_travelers = 4
        session.add(sample_itinerary)
        session.commit()

        # Rollback
        rollback_to_version(session, sample_itinerary, v1)

        # Verify restoration
        session.refresh(sample_itinerary)
        assert sample_itinerary.destination == "Tarifa"
        assert sample_itinerary.start_date == "2026-03-15"
        assert sample_itinerary.end_date == "2026-03-20"
        assert sample_itinerary.num_travelers == 2

    def test_creates_versions_during_rollback(self, session: Session, sample_itinerary: Itinerary):
        """Rollback creates versions for before and after states."""
        v1 = create_version(session, sample_itinerary, "Initial")

        # Modify
        sample_itinerary.destination = "Cape Town"
        session.add(sample_itinerary)
        session.commit()

        # Rollback creates 2 additional versions: before rollback, after rollback
        rollback_to_version(session, sample_itinerary, v1)

        versions = get_versions(session, sample_itinerary.id)
        # Initial (1) + before rollback (2) + after rollback (3)
        assert len(versions) == 3

        # Check the version descriptions
        descriptions = [v.change_description for v in versions]
        assert any("Before rollback" in d for d in descriptions)
        assert any("Rolled back" in d for d in descriptions)
