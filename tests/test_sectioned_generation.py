"""Tests for sectioned itinerary generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.orchestrator import ItineraryOrchestrator
from app.schemas.itinerary_sections import (
    SectionedItinerary,
    OverviewSection,
    FlightsSection,
    AccommodationsSection,
    ActivitiesSection,
    LogisticsSection,
)


class TestGenerateInitialItinerary:
    """Tests for ItineraryOrchestrator.generate_initial_itinerary()."""

    @pytest.fixture
    def orchestrator(self):
        return ItineraryOrchestrator()

    @pytest.mark.asyncio
    async def test_yields_generation_start_event(self, orchestrator):
        """First event should be generation_start with destination."""
        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={},
                changes_made=[],
                cross_section_impacts=[],
            )

            events = []
            async for event in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan an adventure trip",
            ):
                events.append(event)
                if len(events) >= 1:
                    break

            assert events[0]["type"] == "generation_start"
            assert events[0]["destination"] == "Bali"

    @pytest.mark.asyncio
    async def test_dispatches_to_activities_then_logistics(self, orchestrator):
        """Should call activities agent first, then logistics."""
        dispatch_calls = []

        async def mock_dispatch(section, *args, **kwargs):
            dispatch_calls.append(section)
            return MagicMock(
                updated_state={"days": []} if section == "activities" else {},
                changes_made=[],
                cross_section_impacts=[],
            )

        with patch.object(orchestrator, 'dispatch_to_agent', side_effect=mock_dispatch):
            async for _ in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
            ):
                pass

        assert dispatch_calls == ["activities", "logistics"]

    @pytest.mark.asyncio
    async def test_yields_agent_start_events(self, orchestrator):
        """Should yield agent_start for activities and logistics."""
        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={},
                changes_made=[],
                cross_section_impacts=[],
            )

            events = []
            async for event in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
            ):
                events.append(event)

            agent_starts = [e for e in events if e["type"] == "agent_start"]
            assert len(agent_starts) == 2
            assert agent_starts[0]["section"] == "activities"
            assert agent_starts[1]["section"] == "logistics"

    @pytest.mark.asyncio
    async def test_yields_agent_done_events(self, orchestrator):
        """Should yield agent_done after each agent completes."""
        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={"days": []},
                changes_made=["Created activities"],
                cross_section_impacts=[],
            )

            events = []
            async for event in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
            ):
                events.append(event)

            agent_dones = [e for e in events if e["type"] == "agent_done"]
            assert len(agent_dones) == 2
            assert agent_dones[0]["section"] == "activities"
            assert agent_dones[1]["section"] == "logistics"

    @pytest.mark.asyncio
    async def test_yields_validation_event(self, orchestrator):
        """Should yield validation event before done."""
        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={},
                changes_made=[],
                cross_section_impacts=[],
            )

            events = []
            async for event in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
            ):
                events.append(event)

            validation_events = [e for e in events if e["type"] == "validation"]
            assert len(validation_events) == 1
            assert "result" in validation_events[0]
            assert "is_valid" in validation_events[0]["result"]

    @pytest.mark.asyncio
    async def test_yields_done_with_complete_itinerary(self, orchestrator):
        """Final event should be done with full itinerary structure."""
        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={"days": []},
                changes_made=[],
                cross_section_impacts=[],
            )

            events = []
            async for event in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
            ):
                events.append(event)

            done_event = next(e for e in events if e["type"] == "done")
            itinerary = done_event["itinerary"]

            assert itinerary["overview"]["destination"] == "Bali"
            assert itinerary["overview"]["start_date"] == "2026-03-01"
            assert itinerary["overview"]["end_date"] == "2026-03-07"
            assert itinerary["overview"]["num_travelers"] == 2
            assert "flights" in itinerary
            assert "accommodations" in itinerary
            assert "activities" in itinerary
            assert "logistics" in itinerary

    @pytest.mark.asyncio
    async def test_flights_and_accommodations_start_empty(self, orchestrator):
        """Flights and accommodations should be empty in initial generation."""
        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={},
                changes_made=[],
                cross_section_impacts=[],
            )

            events = []
            async for event in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
            ):
                events.append(event)

            done_event = next(e for e in events if e["type"] == "done")
            itinerary = done_event["itinerary"]

            # Flights should be empty
            assert itinerary["flights"]["outbound_flights"] == []
            assert itinerary["flights"]["return_flights"] == []
            # Accommodations should be empty
            assert itinerary["accommodations"]["nights"] == []

    @pytest.mark.asyncio
    async def test_sets_default_title_if_not_provided(self, orchestrator):
        """Should set a default title if not populated by agents."""
        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={},
                changes_made=[],
                cross_section_impacts=[],
            )

            events = []
            async for event in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
            ):
                events.append(event)

            done_event = next(e for e in events if e["type"] == "done")
            itinerary = done_event["itinerary"]

            # Should have a default title
            assert "Bali" in itinerary["overview"]["title"]
            assert "7" in itinerary["overview"]["title"]  # 7 days

    @pytest.mark.asyncio
    async def test_includes_preferences_in_dispatch(self, orchestrator):
        """Should pass preferences to agent dispatch."""
        preferences = {"preferred_activities": ["surfing", "yoga"]}

        with patch.object(orchestrator, 'dispatch_to_agent', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = MagicMock(
                updated_state={},
                changes_made=[],
                cross_section_impacts=[],
            )

            async for _ in orchestrator.generate_initial_itinerary(
                destination="Bali",
                start_date="2026-03-01",
                end_date="2026-03-07",
                num_travelers=2,
                user_request="Plan trip",
                preferences=preferences,
            ):
                pass

            # Both calls should include preferences
            assert mock_dispatch.call_count == 2
            for call in mock_dispatch.call_args_list:
                assert call[1].get("preferences") == preferences or call[0][-1] == preferences


class TestBuildInitialShell:
    """Tests for _build_initial_shell helper."""

    def test_builds_valid_sectioned_itinerary(self):
        """Should build a valid SectionedItinerary."""
        orchestrator = ItineraryOrchestrator()
        shell = orchestrator._build_initial_shell(
            destination="Paris",
            start_date="2026-04-01",
            end_date="2026-04-05",
            num_travelers=3,
        )

        assert isinstance(shell, SectionedItinerary)
        assert shell.overview.destination == "Paris"
        assert shell.overview.start_date == "2026-04-01"
        assert shell.overview.end_date == "2026-04-05"
        assert shell.overview.num_travelers == 3

    def test_shell_has_empty_flights(self):
        """Shell should have empty flights section."""
        orchestrator = ItineraryOrchestrator()
        shell = orchestrator._build_initial_shell(
            destination="Paris",
            start_date="2026-04-01",
            end_date="2026-04-05",
            num_travelers=1,
        )

        assert shell.flights.outbound_flights == []
        assert shell.flights.return_flights == []

    def test_shell_has_empty_accommodations(self):
        """Shell should have empty accommodations section."""
        orchestrator = ItineraryOrchestrator()
        shell = orchestrator._build_initial_shell(
            destination="Paris",
            start_date="2026-04-01",
            end_date="2026-04-05",
            num_travelers=1,
        )

        assert shell.accommodations.nights == []

    def test_shell_has_unique_id(self):
        """Each shell should have a unique ID."""
        orchestrator = ItineraryOrchestrator()
        shell1 = orchestrator._build_initial_shell(
            destination="Paris",
            start_date="2026-04-01",
            end_date="2026-04-05",
            num_travelers=1,
        )
        shell2 = orchestrator._build_initial_shell(
            destination="Paris",
            start_date="2026-04-01",
            end_date="2026-04-05",
            num_travelers=1,
        )

        assert shell1.id != shell2.id


class TestValidateConsistencyForGeneration:
    """Tests for lenient generation validation."""

    def test_allows_empty_activities(self):
        """Should be valid with empty activities section."""
        orchestrator = ItineraryOrchestrator()
        shell = orchestrator._build_initial_shell(
            destination="Tokyo",
            start_date="2026-05-01",
            end_date="2026-05-05",
            num_travelers=2,
        )

        result = orchestrator.validate_consistency_for_generation(shell)

        assert result.is_valid is True
        assert len(result.issues) == 0

    def test_allows_empty_flights(self):
        """Should be valid with empty flights section."""
        orchestrator = ItineraryOrchestrator()
        shell = orchestrator._build_initial_shell(
            destination="Tokyo",
            start_date="2026-05-01",
            end_date="2026-05-05",
            num_travelers=2,
        )

        result = orchestrator.validate_consistency_for_generation(shell)

        assert result.is_valid is True

    def test_allows_empty_accommodations(self):
        """Should be valid with empty accommodations section."""
        orchestrator = ItineraryOrchestrator()
        shell = orchestrator._build_initial_shell(
            destination="Tokyo",
            start_date="2026-05-01",
            end_date="2026-05-05",
            num_travelers=2,
        )

        result = orchestrator.validate_consistency_for_generation(shell)

        assert result.is_valid is True


class TestGenerateEndpoint:
    """Tests for POST /sections/generate endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_generate_endpoint_exists(self, client):
        """Endpoint should exist and accept POST."""
        # We expect it to fail auth/validation, but not 404
        response = client.post("/sections/generate", json={})
        assert response.status_code != 404

    def test_generate_requires_destination(self, client):
        """Should require destination field."""
        response = client.post("/sections/generate", json={
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "message": "Plan a trip",
        })
        assert response.status_code == 422  # Validation error

    def test_generate_requires_start_date(self, client):
        """Should require start_date field."""
        response = client.post("/sections/generate", json={
            "destination": "Bali",
            "end_date": "2026-03-07",
            "message": "Plan a trip",
        })
        assert response.status_code == 422

    def test_generate_requires_end_date(self, client):
        """Should require end_date field."""
        response = client.post("/sections/generate", json={
            "destination": "Bali",
            "start_date": "2026-03-01",
            "message": "Plan a trip",
        })
        assert response.status_code == 422

    def test_generate_requires_message(self, client):
        """Should require message field."""
        response = client.post("/sections/generate", json={
            "destination": "Bali",
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
        })
        assert response.status_code == 422

    def test_generate_has_default_num_travelers(self):
        """Should default num_travelers to 2 if not provided."""
        from app.routers.sections import GenerateSectionedRequest

        # Should not raise - num_travelers has default value
        request = GenerateSectionedRequest(
            destination="Bali",
            start_date="2026-03-01",
            end_date="2026-03-07",
            message="Plan a trip",
        )
        assert request.num_travelers == 2

    def test_generate_request_model_accepts_valid_data(self):
        """Request model should accept all valid fields."""
        from app.routers.sections import GenerateSectionedRequest

        request = GenerateSectionedRequest(
            destination="Bali",
            start_date="2026-03-01",
            end_date="2026-03-07",
            num_travelers=4,
            message="Plan an adventure trip with surfing",
        )
        assert request.destination == "Bali"
        assert request.start_date == "2026-03-01"
        assert request.end_date == "2026-03-07"
        assert request.num_travelers == 4
        assert request.message == "Plan an adventure trip with surfing"
