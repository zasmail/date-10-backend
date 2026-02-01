"""Tests for the geocoding API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestGeocodeLocation:
    """Tests for GET /geocoding/{location} endpoint."""

    def test_geocode_known_destination_tarifa(self, client: TestClient):
        """Test geocoding a known destination from the knowledge base."""
        response = client.get("/geocoding/Tarifa")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Tarifa"
        assert data["lat"] == 36.0143
        assert data["lng"] == -5.6044
        assert data["source"] == "knowledge_base"
        assert data["country"] == "Spain"
        assert data["region"] == "Andalusia"

    def test_geocode_known_destination_cape_town(self, client: TestClient):
        """Test geocoding Cape Town (different coordinates format)."""
        response = client.get("/geocoding/Cape%20Town")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Cape Town"
        assert data["lat"] == -33.9249
        assert data["lng"] == 18.4241
        assert data["source"] == "knowledge_base"
        assert data["country"] == "South Africa"

    def test_geocode_case_insensitive(self, client: TestClient):
        """Test that geocoding is case-insensitive."""
        response = client.get("/geocoding/tarifa")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Tarifa"

    def test_geocode_with_whitespace(self, client: TestClient):
        """Test that geocoding handles leading/trailing whitespace."""
        response = client.get("/geocoding/%20Tarifa%20")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Tarifa"

    def test_geocode_unknown_destination_returns_404(self, client: TestClient):
        """Test that unknown destinations return 404."""
        response = client.get("/geocoding/UnknownCity123")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_geocode_partial_name_not_found(self, client: TestClient):
        """Test that partial matches don't work (exact match required)."""
        response = client.get("/geocoding/Tar")

        assert response.status_code == 404


class TestListKnownLocations:
    """Tests for GET /geocoding endpoint."""

    def test_list_known_locations(self, client: TestClient):
        """Test listing all known locations."""
        response = client.get("/geocoding")

        assert response.status_code == 200
        data = response.json()

        # Should be a list
        assert isinstance(data, list)

        # Should have multiple destinations
        assert len(data) >= 5

        # Check structure of first item
        first = data[0]
        assert "name" in first
        assert "lat" in first
        assert "lng" in first
        assert "source" in first
        assert first["source"] == "knowledge_base"

    def test_list_includes_tarifa(self, client: TestClient):
        """Test that Tarifa is in the list of known locations."""
        response = client.get("/geocoding")

        assert response.status_code == 200
        data = response.json()

        names = [loc["name"] for loc in data]
        assert "Tarifa" in names

    def test_list_all_have_coordinates(self, client: TestClient):
        """Test that all returned locations have valid coordinates."""
        response = client.get("/geocoding")

        assert response.status_code == 200
        data = response.json()

        for loc in data:
            # Latitude should be between -90 and 90
            assert -90 <= loc["lat"] <= 90
            # Longitude should be between -180 and 180
            assert -180 <= loc["lng"] <= 180
