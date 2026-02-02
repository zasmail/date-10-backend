"""Tests for share and export API endpoints."""

import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.database import get_session, engine
from app.models.itinerary import Itinerary
from app.models.shared_itinerary import SharedItinerary
from app.schemas.itinerary import (
    ItineraryProposal,
    ItineraryDay,
    Activity,
    Accommodation,
)


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def sample_itinerary(client):
    """Create a sample itinerary for testing."""
    with Session(engine) as session:
        # Create sample proposal data
        activity = Activity(
            time="09:00",
            name="Beach Surf Session",
            description="Morning surf at Canggu Beach",
            duration="3 hours",
            location="Canggu Beach",
            cost_estimate="$30-50",
            booking_required=False,
        )

        accommodation = Accommodation(
            name="Surf Camp Bali",
            area="Canggu",
            style="Surf camp",
            price_range="$40-60/night",
            notes="Breakfast included",
        )

        day = ItineraryDay(
            day_number=1,
            date="2024-06-01",
            title="Arrival & First Surf",
            location="Canggu, Bali",
            activities=[activity],
            accommodation=accommodation,
            notes="Settle in and catch some waves",
        )

        proposal = ItineraryProposal(
            id="prop-1",
            title="Surf Adventure",
            summary="A week of surfing in Bali's best spots",
            days=[day],
            total_budget_estimate="$1500-2000",
            highlights=["World-class surf breaks", "Vibrant beach culture"],
            caveats=["Crowded during peak season"],
        )

        # Create itinerary
        itinerary = Itinerary(
            id="test-itinerary-1",
            user_id="test-user",
            destination="Bali, Indonesia",
            start_date="2024-06-01",
            end_date="2024-06-07",
            num_travelers=2,
            proposals_json=json.dumps([proposal.model_dump()]),
        )

        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)

        yield itinerary

        # Cleanup
        session.delete(itinerary)
        # Also clean up any shared itineraries
        from sqlmodel import select
        shared_links = session.exec(
            select(SharedItinerary).where(
                SharedItinerary.itinerary_id == itinerary.id
            )
        ).all()
        for link in shared_links:
            session.delete(link)
        session.commit()


class TestExportMarkdown:
    """Tests for markdown export endpoint."""

    def test_export_markdown_success(self, client, sample_itinerary):
        """Test exporting itinerary as markdown."""
        response = client.get(f"/itineraries/{sample_itinerary.id}/export/markdown")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "bali" in response.headers["content-disposition"].lower()

        content = response.text
        assert "# Bali, Indonesia Travel Itinerary" in content
        assert "2024-06-01 to 2024-06-07" in content
        assert "Surf Adventure" in content
        assert "Day 1: Arrival & First Surf" in content
        assert "Beach Surf Session" in content

    def test_export_markdown_not_found(self, client):
        """Test export with non-existent itinerary."""
        response = client.get("/itineraries/nonexistent-id/export/markdown")
        assert response.status_code == 404

    def test_export_markdown_with_proposal_id(self, client, sample_itinerary):
        """Test exporting specific proposal."""
        response = client.get(
            f"/itineraries/{sample_itinerary.id}/export/markdown?proposal_id=prop-1"
        )

        assert response.status_code == 200
        assert "Surf Adventure" in response.text


class TestExportJson:
    """Tests for JSON export endpoint."""

    def test_export_json_success(self, client, sample_itinerary):
        """Test exporting itinerary as JSON."""
        response = client.get(f"/itineraries/{sample_itinerary.id}/export/json")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]

        data = response.json()
        assert data["destination"] == "Bali, Indonesia"
        assert data["start_date"] == "2024-06-01"
        assert data["end_date"] == "2024-06-07"
        assert data["num_travelers"] == 2
        assert len(data["proposals"]) == 1
        assert data["proposals"][0]["title"] == "Surf Adventure"
        assert "metadata" in data
        assert data["metadata"]["generator"] == "Wanderlust"

    def test_export_json_not_found(self, client):
        """Test export with non-existent itinerary."""
        response = client.get("/itineraries/nonexistent-id/export/json")
        assert response.status_code == 404


class TestCreateShareLink:
    """Tests for share link creation endpoint."""

    def test_create_share_link_success(self, client, sample_itinerary):
        """Test creating a share link."""
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/share",
            json={"title": "My Bali Trip"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "share_url" in data
        assert data["title"] == "My Bali Trip"
        assert data["share_url"].startswith("/share/")

    def test_create_share_link_default_title(self, client, sample_itinerary):
        """Test creating share link with default title."""
        response = client.post(
            f"/itineraries/{sample_itinerary.id}/share",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert "Bali" in data["title"]

    def test_create_share_link_returns_existing(self, client, sample_itinerary):
        """Test that creating share link returns existing active link."""
        # Create first link
        response1 = client.post(
            f"/itineraries/{sample_itinerary.id}/share",
            json={"title": "First Title"},
        )
        token1 = response1.json()["token"]

        # Try to create second link - should return same token
        response2 = client.post(
            f"/itineraries/{sample_itinerary.id}/share",
            json={"title": "Second Title"},
        )
        token2 = response2.json()["token"]

        assert token1 == token2

    def test_create_share_link_not_found(self, client):
        """Test creating share link for non-existent itinerary."""
        response = client.post(
            "/itineraries/nonexistent-id/share",
            json={},
        )
        assert response.status_code == 404


class TestGetSharedItinerary:
    """Tests for public shared itinerary endpoint."""

    def test_get_shared_itinerary_success(self, client, sample_itinerary):
        """Test fetching shared itinerary by token."""
        # First create a share link
        share_response = client.post(
            f"/itineraries/{sample_itinerary.id}/share",
            json={"title": "Shared Bali Trip"},
        )
        token = share_response.json()["token"]

        # Fetch shared itinerary
        response = client.get(f"/share/{token}")

        assert response.status_code == 200
        data = response.json()
        assert data["destination"] == "Bali, Indonesia"
        assert data["title"] == "Shared Bali Trip"
        assert data["num_travelers"] == 2
        assert len(data["proposals"]) == 1
        assert data["view_count"] == 1

    def test_get_shared_itinerary_increments_view_count(self, client, sample_itinerary):
        """Test that view count increments on each access."""
        # Create share link
        share_response = client.post(
            f"/itineraries/{sample_itinerary.id}/share",
            json={},
        )
        token = share_response.json()["token"]

        # Access multiple times
        for expected_count in range(1, 4):
            response = client.get(f"/share/{token}")
            assert response.status_code == 200
            assert response.json()["view_count"] == expected_count

    def test_get_shared_itinerary_invalid_token(self, client):
        """Test fetching with invalid token."""
        response = client.get("/share/invalid-token-12345")
        assert response.status_code == 404

    def test_get_shared_itinerary_inactive_link(self, client, sample_itinerary):
        """Test fetching with revoked/inactive link."""
        # Create and then revoke share link
        share_response = client.post(
            f"/itineraries/{sample_itinerary.id}/share",
            json={},
        )
        token = share_response.json()["token"]

        # Revoke the link
        client.delete(f"/itineraries/{sample_itinerary.id}/share")

        # Try to fetch - should fail
        response = client.get(f"/share/{token}")
        assert response.status_code == 404


class TestRevokeShareLink:
    """Tests for revoking share links."""

    def test_revoke_share_link_success(self, client, sample_itinerary):
        """Test revoking a share link."""
        # Create share link
        client.post(f"/itineraries/{sample_itinerary.id}/share", json={})

        # Revoke it
        response = client.delete(f"/itineraries/{sample_itinerary.id}/share")

        assert response.status_code == 200
        assert "revoked" in response.json()["message"].lower()

    def test_revoke_share_link_not_found(self, client, sample_itinerary):
        """Test revoking when no active link exists."""
        response = client.delete(f"/itineraries/{sample_itinerary.id}/share")
        assert response.status_code == 404
