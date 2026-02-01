"""Tests for itinerary API endpoints."""

import pytest
import json
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import Itinerary


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
        {
            "id": "prop-2",
            "title": "Relaxed",
            "summary": "Chill vibes",
            "days": [],
            "total_budget_estimate": "$1200",
            "highlights": ["Beach"],
            "caveats": ["Less activity"],
        },
    ]

    itinerary = Itinerary(
        destination="Tarifa",
        start_date="2026-03-15",
        end_date="2026-03-20",
        proposals_json=json.dumps(proposals),
    )
    session.add(itinerary)
    session.commit()
    session.refresh(itinerary)
    return itinerary


class TestListItineraries:
    """Tests for GET /itineraries."""

    def test_empty_list(self, client: TestClient):
        """Empty list when no itineraries."""
        response = client.get("/itineraries")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_itinerary(self, client: TestClient, sample_itinerary: Itinerary):
        """List includes created itinerary."""
        response = client.get("/itineraries")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["destination"] == "Tarifa"


class TestGetItinerary:
    """Tests for GET /itineraries/{id}."""

    def test_get_existing(self, client: TestClient, sample_itinerary: Itinerary):
        """Get existing itinerary by ID."""
        response = client.get(f"/itineraries/{sample_itinerary.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["destination"] == "Tarifa"
        assert len(data["proposals"]) == 2

    def test_get_nonexistent(self, client: TestClient):
        """404 for nonexistent itinerary."""
        response = client.get("/itineraries/nonexistent-id")
        assert response.status_code == 404


class TestSelectProposal:
    """Tests for POST /itineraries/{id}/select."""

    def test_select_valid_proposal(self, client: TestClient, sample_itinerary: Itinerary):
        """Select a valid proposal."""
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/select", json={"proposal_id": "prop-1"}
        )
        assert response.status_code == 200
        assert response.json()["selected_proposal_id"] == "prop-1"

    def test_select_invalid_proposal(self, client: TestClient, sample_itinerary: Itinerary):
        """400 for invalid proposal ID."""
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/select", json={"proposal_id": "invalid-id"}
        )
        assert response.status_code == 400

    def test_select_nonexistent_itinerary(self, client: TestClient):
        """404 for nonexistent itinerary."""
        response = client.post("/itineraries/nonexistent/select", json={"proposal_id": "prop-1"})
        assert response.status_code == 404


class TestDeleteItinerary:
    """Tests for DELETE /itineraries/{id}."""

    def test_delete_existing(
        self, client: TestClient, sample_itinerary: Itinerary, session: Session
    ):
        """Delete existing itinerary."""
        response = client.delete(f"/itineraries/{sample_itinerary.id}")
        assert response.status_code == 200

        # Verify deleted
        response = client.get(f"/itineraries/{sample_itinerary.id}")
        assert response.status_code == 404

    def test_delete_nonexistent(self, client: TestClient):
        """404 for nonexistent itinerary."""
        response = client.delete("/itineraries/nonexistent")
        assert response.status_code == 404
