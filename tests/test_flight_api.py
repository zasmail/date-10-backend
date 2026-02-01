"""Tests for flight API endpoints."""

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
            "days": [
                {
                    "day_number": 1,
                    "date": "2026-05-15",
                    "location": "Tarifa",
                    "title": "Day 1",
                    "activities": [],
                },
                {
                    "day_number": 2,
                    "date": "2026-05-16",
                    "location": "Tarifa",
                    "title": "Day 2",
                    "activities": [],
                },
            ],
            "total_budget_estimate": "$1500",
            "highlights": ["Surfing"],
            "caveats": ["Weather"],
        }
    ]

    itinerary = Itinerary(
        destination="Tarifa",
        start_date="2026-05-15",
        end_date="2026-05-20",
        proposals_json=json.dumps(proposals),
    )
    session.add(itinerary)
    session.commit()
    session.refresh(itinerary)
    return itinerary


class TestIataLookup:
    """Tests for GET /flights/iata/{destination}."""

    def test_known_destination(self, client: TestClient):
        """Lookup known destination."""
        response = client.get("/flights/iata/tarifa")
        assert response.status_code == 200
        data = response.json()
        assert data["iata_code"] == "AGP"

    def test_unknown_destination(self, client: TestClient):
        """Lookup unknown destination."""
        response = client.get("/flights/iata/unknown")
        assert response.status_code == 200
        data = response.json()
        assert data["iata_code"] is None


class TestSearchFlights:
    """Tests for POST /flights/search."""

    def test_empty_segments_rejected(self, client: TestClient):
        """Empty segments returns 400."""
        response = client.post(
            "/flights/search",
            json={"segments": [], "travellers": ["ADT"], "currency": "USD"},
        )
        assert response.status_code == 400


class TestItineraryFlights:
    """Tests for POST /flights/itinerary/{id}."""

    def test_nonexistent_itinerary(self, client: TestClient):
        """Nonexistent itinerary returns 404."""
        response = client.post("/flights/itinerary/nonexistent?origin=JFK")
        assert response.status_code == 404
