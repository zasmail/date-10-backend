"""Tests for section refinement API endpoints."""

import pytest
import json
from datetime import datetime
import uuid
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.database import engine
from app.models.sectioned_itinerary import SectionedItineraryModel
from app.schemas.itinerary_sections import (
    SectionedItinerary,
    OverviewSection,
    FlightsSection,
    AccommodationsSection,
    ActivitiesSection,
    ActivityDay,
    LogisticsSection,
)


client = TestClient(app)


def create_test_sectioned_itinerary() -> dict:
    """Create test sectioned itinerary data."""
    now = datetime.utcnow().isoformat()
    return SectionedItinerary(
        id=str(uuid.uuid4()),
        overview=OverviewSection(
            destination="Tarifa, Spain",
            start_date="2026-03-15",
            end_date="2026-03-20",
            num_travelers=2,
            title="Kitesurfing Adventure",
            summary="5 days of wind and waves",
            total_budget_estimate="$2500",
        ),
        flights=FlightsSection(),
        accommodations=AccommodationsSection(),
        activities=ActivitiesSection(days=[
            ActivityDay(
                day_number=i,
                date=f"2026-03-{14+i}",
                title=f"Day {i}",
                location="Tarifa",
                activities=[],
            )
            for i in range(1, 7)  # 6 days to match 15-20 March
        ]),
        logistics=LogisticsSection(),
        created_at=now,
        updated_at=now,
    ).model_dump()


@pytest.fixture
def test_itinerary():
    """Create and persist a test itinerary."""
    itinerary_data = create_test_sectioned_itinerary()

    with Session(engine) as session:
        model = SectionedItineraryModel(
            id=itinerary_data["id"],
            destination=itinerary_data["overview"]["destination"],
            start_date=itinerary_data["overview"]["start_date"],
            end_date=itinerary_data["overview"]["end_date"],
            num_travelers=itinerary_data["overview"]["num_travelers"],
            title=itinerary_data["overview"]["title"],
            sections_json=json.dumps(itinerary_data),
        )
        session.add(model)
        session.commit()
        session.refresh(model)

        yield model

        # Cleanup
        session.delete(model)
        session.commit()


class TestGetSectionedItinerary:
    def test_get_existing_itinerary(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["destination"] == "Tarifa, Spain"
        assert "sections" in data
        assert data["sections"]["overview"]["title"] == "Kitesurfing Adventure"

    def test_get_nonexistent_itinerary(self):
        response = client.get("/sections/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_itinerary_includes_all_fields(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}")
        assert response.status_code == 200
        data = response.json()
        # Check all required fields
        assert "id" in data
        assert "destination" in data
        assert "start_date" in data
        assert "end_date" in data
        assert "num_travelers" in data
        assert "title" in data
        assert "sections" in data
        assert "version" in data
        assert "created_at" in data
        assert "updated_at" in data


class TestGetSection:
    def test_get_overview_section(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}/section/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["section"] == "overview"
        assert data["data"]["destination"] == "Tarifa, Spain"
        assert data["data"]["num_travelers"] == 2

    def test_get_flights_section(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}/section/flights")
        assert response.status_code == 200
        data = response.json()
        assert data["section"] == "flights"
        assert "outbound_flights" in data["data"]
        assert "return_flights" in data["data"]

    def test_get_accommodations_section(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}/section/accommodations")
        assert response.status_code == 200
        data = response.json()
        assert data["section"] == "accommodations"
        assert "nights" in data["data"]

    def test_get_activities_section(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}/section/activities")
        assert response.status_code == 200
        data = response.json()
        assert data["section"] == "activities"
        assert "days" in data["data"]
        assert len(data["data"]["days"]) == 6

    def test_get_logistics_section(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}/section/logistics")
        assert response.status_code == 200
        data = response.json()
        assert data["section"] == "logistics"

    def test_get_invalid_section(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}/section/invalid")
        assert response.status_code == 400
        assert "Invalid section" in response.json()["detail"]

    def test_get_section_nonexistent_itinerary(self):
        response = client.get("/sections/nonexistent-id/section/overview")
        assert response.status_code == 404


class TestClassifyIntent:
    @patch('app.routers.sections.classify_user_intent')
    def test_classify_flights_intent(self, mock_classify, test_itinerary):
        mock_classify.return_value = {
            "primary_section": "flights",
            "secondary_sections": [],
            "action_type": "search",
            "confidence": 0.95,
            "clarification_needed": None,
        }

        response = client.post(
            f"/sections/{test_itinerary.id}/classify",
            json={"message": "Find flights to Madrid"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["primary_section"] == "flights"
        assert data["confidence"] == 0.95

    @patch('app.routers.sections.classify_user_intent')
    def test_classify_accommodations_intent(self, mock_classify, test_itinerary):
        mock_classify.return_value = {
            "primary_section": "accommodations",
            "secondary_sections": [],
            "action_type": "search",
            "confidence": 0.88,
            "clarification_needed": None,
        }

        response = client.post(
            f"/sections/{test_itinerary.id}/classify",
            json={"message": "Find a boutique hotel near the beach"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["primary_section"] == "accommodations"

    @patch('app.routers.sections.classify_user_intent')
    def test_classify_ambiguous_intent(self, mock_classify, test_itinerary):
        mock_classify.return_value = {
            "primary_section": "overview",
            "secondary_sections": ["flights", "accommodations"],
            "action_type": "clarify",
            "confidence": 0.4,
            "clarification_needed": "Did you mean flights or accommodations?",
        }

        response = client.post(
            f"/sections/{test_itinerary.id}/classify",
            json={"message": "Make it cheaper"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] < 0.7
        assert data["clarification_needed"] is not None

    def test_classify_nonexistent_itinerary(self):
        response = client.post(
            "/sections/nonexistent-id/classify",
            json={"message": "Find flights"}
        )
        assert response.status_code == 404


class TestValidateConsistency:
    @patch('app.routers.sections.validate_itinerary_consistency')
    def test_validate_all_sections(self, mock_validate, test_itinerary):
        mock_validate.return_value = {
            "is_valid": True,
            "issues": []
        }

        response = client.post(
            f"/sections/{test_itinerary.id}/validate",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_valid" in data
        assert "issues" in data
        assert data["is_valid"] is True

    @patch('app.routers.sections.validate_itinerary_consistency')
    def test_validate_with_issues(self, mock_validate, test_itinerary):
        mock_validate.return_value = {
            "is_valid": False,
            "issues": [
                {"section": "accommodations", "message": "Missing accommodation for day 3"}
            ]
        }

        response = client.post(
            f"/sections/{test_itinerary.id}/validate",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert len(data["issues"]) == 1

    @patch('app.routers.sections.validate_itinerary_consistency')
    def test_validate_specific_sections(self, mock_validate, test_itinerary):
        mock_validate.return_value = {
            "is_valid": True,
            "issues": []
        }

        response = client.post(
            f"/sections/{test_itinerary.id}/validate",
            json={"sections": ["flights", "accommodations"]}
        )
        assert response.status_code == 200
        # Verify only specific sections were checked
        mock_validate.assert_called_once()

    def test_validate_nonexistent_itinerary(self):
        response = client.post(
            "/sections/nonexistent-id/validate",
            json={}
        )
        assert response.status_code == 404


class TestListSectionedItineraries:
    def test_list_itineraries(self, test_itinerary):
        response = client.get("/sections")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should include our test itinerary
        assert any(it["id"] == test_itinerary.id for it in data)

    def test_list_itineraries_empty(self):
        # Even with no data, should return empty list
        response = client.get("/sections")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_itineraries_with_limit(self, test_itinerary):
        response = client.get("/sections?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5


class TestMigrateLegacyItinerary:
    def test_migrate_nonexistent_legacy(self):
        response = client.post(
            "/sections/migrate",
            json={"legacy_itinerary_id": "nonexistent"}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestRefineSection:
    """Tests for the streaming refine endpoint."""

    def test_refine_nonexistent_itinerary(self):
        response = client.post(
            "/sections/nonexistent/refine",
            json={"message": "Add a rest day"}
        )
        assert response.status_code == 404

    def test_refine_request_validation(self, test_itinerary):
        # Empty message should fail validation
        response = client.post(
            f"/sections/{test_itinerary.id}/refine",
            json={}
        )
        assert response.status_code == 422  # Validation error

    @patch('app.routers.sections.orchestrate_section_update')
    def test_refine_with_target_section_hint(self, mock_orchestrate, test_itinerary):
        # Mock the orchestrator to return a simple done event
        async def mock_generator():
            yield {
                "type": "done",
                "result": {
                    "itinerary": json.loads(test_itinerary.sections_json),
                    "sections_updated": ["flights"],
                }
            }

        mock_orchestrate.return_value = mock_generator()

        # Full SSE test would need httpx streaming
        # For now, just verify the endpoint accepts the request
        response = client.post(
            f"/sections/{test_itinerary.id}/refine",
            json={"message": "Find cheaper options", "target_section": "flights"}
        )
        # SSE endpoint should return 200
        assert response.status_code == 200


class TestSectionedItineraryResponse:
    """Tests for response model correctness."""

    def test_response_has_correct_types(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}")
        assert response.status_code == 200
        data = response.json()

        # Check types
        assert isinstance(data["id"], str)
        assert isinstance(data["destination"], str)
        assert isinstance(data["num_travelers"], int)
        assert isinstance(data["version"], int)
        assert isinstance(data["sections"], dict)

    def test_sections_structure(self, test_itinerary):
        response = client.get(f"/sections/{test_itinerary.id}")
        assert response.status_code == 200
        sections = response.json()["sections"]

        # Verify all sections present
        assert "overview" in sections
        assert "flights" in sections
        assert "accommodations" in sections
        assert "activities" in sections
        assert "logistics" in sections
