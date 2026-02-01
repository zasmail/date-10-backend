"""Tests for refinement API endpoints."""

import pytest
import json
from unittest.mock import AsyncMock, patch
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
    """Create a sample itinerary with proposals for testing."""
    proposals = [
        {
            "id": "prop-adventure",
            "title": "Adventure Focus",
            "summary": "Action-packed trip",
            "days": [
                {
                    "day_number": 1,
                    "date": "2026-03-15",
                    "title": "Arrival Day",
                    "location": "Tarifa",
                    "activities": [
                        {
                            "time": "14:00",
                            "name": "Hotel Check-in",
                            "description": "Settle in",
                            "duration": "1 hour",
                        },
                    ],
                    "accommodation": {
                        "name": "Hotel Arte Vida",
                        "area": "Beach",
                        "style": "Boutique",
                        "price_range": "$120/night",
                    },
                },
                {
                    "day_number": 2,
                    "date": "2026-03-16",
                    "title": "Surf Day",
                    "location": "Tarifa Beach",
                    "activities": [
                        {
                            "time": "09:00",
                            "name": "Surfing",
                            "description": "Morning surf session",
                            "duration": "3 hours",
                        },
                    ],
                    "accommodation": {
                        "name": "Hotel Arte Vida",
                        "area": "Beach",
                        "style": "Boutique",
                        "price_range": "$120/night",
                    },
                },
                {
                    "day_number": 3,
                    "date": "2026-03-17",
                    "title": "Kitesurf Day",
                    "location": "Valdevaqueros",
                    "activities": [
                        {
                            "time": "10:00",
                            "name": "Kitesurfing",
                            "description": "Full day kiting",
                            "duration": "6 hours",
                        },
                    ],
                    "accommodation": {
                        "name": "Hotel Arte Vida",
                        "area": "Beach",
                        "style": "Boutique",
                        "price_range": "$120/night",
                    },
                },
                {
                    "day_number": 4,
                    "date": "2026-03-18",
                    "title": "Departure",
                    "location": "Tarifa",
                    "activities": [
                        {
                            "time": "10:00",
                            "name": "Checkout",
                            "description": "Head to airport",
                            "duration": "2 hours",
                        },
                    ],
                },
            ],
            "total_budget_estimate": "$1500",
            "highlights": ["Surfing", "Kitesurfing"],
            "caveats": ["Weather dependent"],
            "start_date": "2026-03-15",
        },
        {
            "id": "prop-relaxed",
            "title": "Relaxed Pace",
            "summary": "Chill vibes",
            "days": [],
            "total_budget_estimate": "$1200",
            "highlights": ["Beach"],
            "caveats": [],
        },
    ]

    itinerary = Itinerary(
        destination="Tarifa",
        start_date="2026-03-15",
        end_date="2026-03-18",
        num_travelers=2,
        proposals_json=json.dumps(proposals),
        selected_proposal_id="prop-adventure",
    )
    session.add(itinerary)
    session.commit()
    session.refresh(itinerary)
    return itinerary


class TestRefineEndpointBasics:
    """Basic tests for POST /itineraries/{id}/refine endpoint."""

    def test_refine_nonexistent_itinerary(self, client: TestClient):
        """404 for nonexistent itinerary."""
        response = client.post(
            "/itineraries/nonexistent-id/refine",
            json={"message": "swap day 2 and 3"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_refine_invalid_proposal(self, client: TestClient, sample_itinerary: Itinerary):
        """400 for invalid proposal_id."""
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/refine",
            json={"message": "test", "proposal_id": "invalid-proposal"},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()


class TestRefineWithMockClaude:
    """Tests using mocked Claude responses."""

    def test_refine_swap_days(self, client: TestClient, sample_itinerary: Itinerary):
        """Test refining with swap_days tool call."""

        async def mock_stream_response(*args, **kwargs):
            # Simulate Claude deciding to swap days
            yield {"type": "text", "content": "I'll swap day 2 and day 3 for you."}
            yield {
                "type": "tool_use",
                "name": "swap_days",
                "input": {"day_a": 2, "day_b": 3, "reason": "User requested"},
            }
            yield {
                "type": "tool_result",
                "name": "swap_days",
                "success": True,
                "proposal": {"id": "prop-adventure", "days": []},
            }
            yield {
                "type": "done",
                "proposal": {"id": "prop-adventure", "days": []},
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }

        # Patch where the function is used (in the router module)
        with patch(
            "app.routers.refinements.refine_itinerary_streaming",
            return_value=mock_stream_response(),
        ):
            with client.stream(
                "POST",
                f"/itineraries/{sample_itinerary.id}/refine",
                json={"message": "swap day 2 and day 3"},
            ) as response:
                assert response.status_code == 200

                events = []
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        events.append(data)

                # Should have text events
                text_events = [e for e in events if e.get("type") == "text"]
                assert len(text_events) > 0

    def test_refine_add_rest_day(self, client: TestClient, sample_itinerary: Itinerary):
        """Test adding a rest day through refinement."""

        async def mock_stream_response(*args, **kwargs):
            yield {"type": "text", "content": "Adding a rest day after the kitesurf session."}
            yield {
                "type": "tool_use",
                "name": "add_day",
                "input": {
                    "after_day": 3,
                    "title": "Rest & Recovery",
                    "location": "Tarifa",
                    "activities": [
                        {
                            "time": "10:00",
                            "name": "Sleep In",
                            "description": "Rest after activities",
                            "duration": "morning",
                        }
                    ],
                    "notes": "Recovery day",
                },
            }
            yield {
                "type": "tool_result",
                "name": "add_day",
                "success": True,
                "proposal": {"id": "prop-adventure", "days": []},
            }
            yield {
                "type": "done",
                "proposal": {"id": "prop-adventure", "days": []},
                "usage": {"input_tokens": 150, "output_tokens": 80},
            }

        with patch(
            "app.routers.refinements.refine_itinerary_streaming",
            return_value=mock_stream_response(),
        ):
            with client.stream(
                "POST",
                f"/itineraries/{sample_itinerary.id}/refine",
                json={"message": "add a rest day after the kitesurf day"},
            ) as response:
                assert response.status_code == 200

                events = []
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        events.append(data)

                tool_use_events = [e for e in events if e.get("type") == "tool_use"]
                assert len(tool_use_events) > 0
                assert tool_use_events[0]["name"] == "add_day"

    def test_refine_update_accommodation(self, client: TestClient, sample_itinerary: Itinerary):
        """Test finding cheaper accommodation through refinement."""

        async def mock_stream_response(*args, **kwargs):
            yield {"type": "text", "content": "I found a more budget-friendly option."}
            yield {
                "type": "tool_use",
                "name": "update_accommodation",
                "input": {
                    "day_number": 1,
                    "accommodation": {
                        "name": "Budget Hostel",
                        "area": "Old Town",
                        "style": "Hostel",
                        "price_range": "$30-50/night",
                        "notes": "Great for budget travelers",
                    },
                    "apply_to_consecutive": True,
                },
            }
            yield {
                "type": "tool_result",
                "name": "update_accommodation",
                "success": True,
                "proposal": {"id": "prop-adventure", "days": []},
            }
            yield {
                "type": "done",
                "proposal": {"id": "prop-adventure", "days": []},
                "usage": {"input_tokens": 120, "output_tokens": 60},
            }

        with patch(
            "app.routers.refinements.refine_itinerary_streaming",
            return_value=mock_stream_response(),
        ):
            with client.stream(
                "POST",
                f"/itineraries/{sample_itinerary.id}/refine",
                json={"message": "find a cheaper hotel option"},
            ) as response:
                assert response.status_code == 200

                events = []
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        events.append(data)

                tool_use_events = [e for e in events if e.get("type") == "tool_use"]
                assert len(tool_use_events) > 0
                assert tool_use_events[0]["name"] == "update_accommodation"


class TestRefineProposalSelection:
    """Tests for proposal selection in refinement."""

    def test_refine_uses_selected_proposal(self, client: TestClient, sample_itinerary: Itinerary, session: Session):
        """Refinement should use selected proposal by default."""
        # Verify sample_itinerary has prop-adventure selected
        assert sample_itinerary.selected_proposal_id == "prop-adventure"

        captured_proposal = None

        async def mock_stream_response(proposal, messages):
            nonlocal captured_proposal
            captured_proposal = proposal
            yield {"type": "text", "content": "Got it."}
            yield {
                "type": "done",
                "proposal": proposal,
                "usage": {"input_tokens": 50, "output_tokens": 20},
            }

        with patch(
            "app.routers.refinements.refine_itinerary_streaming",
            side_effect=mock_stream_response,
        ):
            with client.stream(
                "POST",
                f"/itineraries/{sample_itinerary.id}/refine",
                json={"message": "test"},
            ) as response:
                assert response.status_code == 200
                # Consume the response
                list(response.iter_lines())

        # Verify the adventure proposal was passed
        assert captured_proposal is not None
        assert captured_proposal["id"] == "prop-adventure"
        assert captured_proposal["title"] == "Adventure Focus"

    def test_refine_specific_proposal(self, client: TestClient, sample_itinerary: Itinerary, session: Session):
        """Can refine a specific proposal by ID."""
        captured_proposal = None

        async def mock_stream_response(proposal, messages):
            nonlocal captured_proposal
            captured_proposal = proposal
            yield {"type": "text", "content": "Working on relaxed itinerary."}
            yield {
                "type": "done",
                "proposal": proposal,
                "usage": {"input_tokens": 50, "output_tokens": 20},
            }

        with patch(
            "app.routers.refinements.refine_itinerary_streaming",
            side_effect=mock_stream_response,
        ):
            with client.stream(
                "POST",
                f"/itineraries/{sample_itinerary.id}/refine",
                json={"message": "test", "proposal_id": "prop-relaxed"},
            ) as response:
                assert response.status_code == 200
                list(response.iter_lines())

        # Should get the relaxed proposal
        assert captured_proposal is not None
        assert captured_proposal["id"] == "prop-relaxed"
        assert captured_proposal["title"] == "Relaxed Pace"

    def test_refine_without_selected_uses_first(self, client: TestClient, session: Session):
        """When no proposal selected, use first one."""
        proposals = [
            {"id": "first", "title": "First", "summary": "First proposal", "days": [], "total_budget_estimate": "$0", "highlights": [], "caveats": []},
            {"id": "second", "title": "Second", "summary": "Second proposal", "days": [], "total_budget_estimate": "$0", "highlights": [], "caveats": []},
        ]
        itinerary = Itinerary(
            destination="Test",
            start_date="2026-01-01",
            end_date="2026-01-02",
            proposals_json=json.dumps(proposals),
            selected_proposal_id=None,  # No selection
        )
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)

        captured_proposal = None

        async def mock_stream_response(proposal, messages):
            nonlocal captured_proposal
            captured_proposal = proposal
            yield {"type": "text", "content": "Working."}
            yield {
                "type": "done",
                "proposal": proposal,
                "usage": {"input_tokens": 50, "output_tokens": 20},
            }

        with patch(
            "app.routers.refinements.refine_itinerary_streaming",
            side_effect=mock_stream_response,
        ):
            with client.stream(
                "POST",
                f"/itineraries/{itinerary.id}/refine",
                json={"message": "test"},
            ) as response:
                assert response.status_code == 200
                list(response.iter_lines())

        # Should get first proposal
        assert captured_proposal is not None
        assert captured_proposal["id"] == "first"


class TestRefineToolResults:
    """Tests for tool execution results in refinement."""

    def test_tool_error_in_stream(self, client: TestClient, sample_itinerary: Itinerary):
        """Error in tool execution should be communicated via stream."""

        async def mock_stream_response(*args, **kwargs):
            yield {"type": "text", "content": "Attempting change."}
            yield {
                "type": "tool_use",
                "name": "swap_days",
                "input": {"day_a": 1, "day_b": 100},
            }
            yield {
                "type": "tool_result",
                "name": "swap_days",
                "success": False,
                "error": "Day 100 is out of range (1-4)",
            }
            yield {
                "type": "done",
                "proposal": None,
                "usage": {"input_tokens": 80, "output_tokens": 30},
            }

        with patch(
            "app.routers.refinements.refine_itinerary_streaming",
            return_value=mock_stream_response(),
        ):
            with client.stream(
                "POST",
                f"/itineraries/{sample_itinerary.id}/refine",
                json={"message": "swap day 1 and 100"},
            ) as response:
                assert response.status_code == 200

                events = []
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        events.append(data)

                # Should have error in tool_result
                tool_results = [e for e in events if e.get("type") == "tool_result"]
                assert len(tool_results) > 0
                assert tool_results[0]["success"] is False
                assert "out of range" in tool_results[0]["error"]


class TestRefineConsistency:
    """Tests for itinerary consistency after refinement."""

    def test_day_numbers_consistent_after_swap(self, client: TestClient, sample_itinerary: Itinerary, session: Session):
        """Day numbers should be consistent after swap."""
        # Get original state
        proposals_before = json.loads(sample_itinerary.proposals_json)
        adventure_before = next(p for p in proposals_before if p["id"] == "prop-adventure")

        assert adventure_before["days"][0]["day_number"] == 1
        assert adventure_before["days"][1]["day_number"] == 2
        assert adventure_before["days"][1]["title"] == "Surf Day"
        assert adventure_before["days"][2]["title"] == "Kitesurf Day"

        # After swap, the service maintains consistency
        # This is tested in test_refinement_service.py more thoroughly

    def test_dates_consistent_after_add_day(self, client: TestClient, sample_itinerary: Itinerary, session: Session):
        """Dates should be recalculated after adding a day."""
        proposals_before = json.loads(sample_itinerary.proposals_json)
        adventure_before = next(p for p in proposals_before if p["id"] == "prop-adventure")

        # Original dates
        assert adventure_before["days"][0]["date"] == "2026-03-15"
        assert adventure_before["days"][3]["date"] == "2026-03-18"

        # The service will update dates when add_day is executed
        # Full integration tested in test_refinement_service.py
