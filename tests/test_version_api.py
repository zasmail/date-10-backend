"""Tests for version API endpoints."""

import pytest
import json
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import Itinerary
from app.models.itinerary_version import ItineraryVersion
from app.services.version_service import create_version


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


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create a test client with overridden session."""

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


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


@pytest.fixture
def itinerary_with_versions(session: Session, sample_itinerary: Itinerary):
    """Create itinerary with several versions."""
    create_version(session, sample_itinerary, "Version 1")
    create_version(session, sample_itinerary, "Version 2")
    create_version(session, sample_itinerary, "Version 3")
    return sample_itinerary


class TestListVersions:
    """Tests for GET /itineraries/{id}/versions."""

    def test_empty_list_when_no_versions(self, client: TestClient, sample_itinerary: Itinerary):
        """Returns empty list when no versions exist."""
        response = client.get(f"/itineraries/{sample_itinerary.id}/versions")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_versions_newest_first(
        self, client: TestClient, itinerary_with_versions: Itinerary
    ):
        """Returns versions in descending order by version_number."""
        response = client.get(f"/itineraries/{itinerary_with_versions.id}/versions")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 3
        assert data[0]["version_number"] == 3
        assert data[1]["version_number"] == 2
        assert data[2]["version_number"] == 1

    def test_version_summary_fields(
        self, client: TestClient, itinerary_with_versions: Itinerary
    ):
        """Version summary includes expected fields."""
        response = client.get(f"/itineraries/{itinerary_with_versions.id}/versions")
        assert response.status_code == 200

        version = response.json()[0]
        assert "id" in version
        assert "version_number" in version
        assert "destination" in version
        assert "start_date" in version
        assert "end_date" in version
        assert "change_description" in version
        assert "created_at" in version

    def test_404_for_nonexistent_itinerary(self, client: TestClient):
        """Returns 404 for nonexistent itinerary."""
        response = client.get("/itineraries/nonexistent/versions")
        assert response.status_code == 404


class TestGetVersionDetail:
    """Tests for GET /itineraries/{id}/versions/{version_id}."""

    def test_returns_version_detail(
        self, client: TestClient, session: Session, sample_itinerary: Itinerary
    ):
        """Returns full version detail including proposals."""
        version = create_version(session, sample_itinerary, "Test version")

        response = client.get(
            f"/itineraries/{sample_itinerary.id}/versions/{version.id}"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == version.id
        assert data["itinerary_id"] == sample_itinerary.id
        assert data["version_number"] == 1
        assert data["destination"] == "Tarifa"
        assert data["num_travelers"] == 2
        assert data["change_description"] == "Test version"
        assert "proposals" in data
        assert isinstance(data["proposals"], list)

    def test_404_for_nonexistent_itinerary(self, client: TestClient):
        """Returns 404 for nonexistent itinerary."""
        response = client.get("/itineraries/nonexistent/versions/version-id")
        assert response.status_code == 404

    def test_404_for_nonexistent_version(
        self, client: TestClient, sample_itinerary: Itinerary
    ):
        """Returns 404 for nonexistent version."""
        response = client.get(
            f"/itineraries/{sample_itinerary.id}/versions/nonexistent"
        )
        assert response.status_code == 404

    def test_404_for_version_from_different_itinerary(
        self, client: TestClient, session: Session, sample_itinerary: Itinerary
    ):
        """Returns 404 when version belongs to different itinerary."""
        # Create another itinerary with a version
        other_itinerary = Itinerary(
            destination="Bali",
            start_date="2026-04-01",
            end_date="2026-04-10",
            proposals_json="[]",
        )
        session.add(other_itinerary)
        session.commit()
        session.refresh(other_itinerary)
        other_version = create_version(session, other_itinerary, "Other")

        # Try to access other version through sample_itinerary
        response = client.get(
            f"/itineraries/{sample_itinerary.id}/versions/{other_version.id}"
        )
        assert response.status_code == 404


class TestRollbackEndpoint:
    """Tests for POST /itineraries/{id}/versions/{version_id}/rollback."""

    def test_rollback_restores_state(
        self, client: TestClient, session: Session, sample_itinerary: Itinerary
    ):
        """Rollback restores itinerary to previous state."""
        # Create initial version
        v1 = create_version(session, sample_itinerary, "Initial")

        # Modify itinerary
        sample_itinerary.destination = "Cape Town"
        session.add(sample_itinerary)
        session.commit()

        # Rollback via API
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/versions/{v1.id}/rollback"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["rolled_back_to_version"] == 1

        # Verify itinerary was restored
        get_response = client.get(f"/itineraries/{sample_itinerary.id}")
        assert get_response.json()["destination"] == "Tarifa"

    def test_rollback_response_format(
        self, client: TestClient, session: Session, sample_itinerary: Itinerary
    ):
        """Rollback response has expected format."""
        v1 = create_version(session, sample_itinerary, "Initial")

        response = client.post(
            f"/itineraries/{sample_itinerary.id}/versions/{v1.id}/rollback"
        )
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "message" in data
        assert "itinerary_id" in data
        assert "rolled_back_to_version" in data

    def test_404_for_nonexistent_itinerary(self, client: TestClient):
        """Returns 404 for nonexistent itinerary."""
        response = client.post("/itineraries/nonexistent/versions/version-id/rollback")
        assert response.status_code == 404

    def test_404_for_nonexistent_version(
        self, client: TestClient, sample_itinerary: Itinerary
    ):
        """Returns 404 for nonexistent version."""
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/versions/nonexistent/rollback"
        )
        assert response.status_code == 404

    def test_404_for_version_from_different_itinerary(
        self, client: TestClient, session: Session, sample_itinerary: Itinerary
    ):
        """Returns 404 when version belongs to different itinerary."""
        # Create another itinerary with a version
        other_itinerary = Itinerary(
            destination="Bali",
            start_date="2026-04-01",
            end_date="2026-04-10",
            proposals_json="[]",
        )
        session.add(other_itinerary)
        session.commit()
        session.refresh(other_itinerary)
        other_version = create_version(session, other_itinerary, "Other")

        # Try to rollback with version from different itinerary
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/versions/{other_version.id}/rollback"
        )
        assert response.status_code == 404
