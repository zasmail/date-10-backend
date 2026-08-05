"""Tests for orchestrator agent and service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import uuid

from app.agents.orchestrator import (
    ItineraryOrchestrator,
    IntentClassification,
    ConsistencyIssue,
    ValidationResult,
    OrchestratorResult,
)
from app.schemas.itinerary_sections import (
    SectionedItinerary,
    OverviewSection,
    FlightsSection,
    AccommodationsSection,
    ActivitiesSection,
    ActivityDay,
    LogisticsSection,
)
from app.services.orchestrator_service import (
    classify_user_intent,
    validate_itinerary_consistency,
)


def create_test_itinerary(with_activities: bool = False) -> SectionedItinerary:
    """Create a test itinerary for tests.

    Args:
        with_activities: If True, creates itinerary with matching activity days.
                        If False, creates with empty activities (valid for initial creation).
    """
    base_itinerary = {
        "id": str(uuid.uuid4()),
        "overview": OverviewSection(
            destination="Tarifa, Spain",
            start_date="2026-03-15",
            end_date="2026-03-17",  # 3-day trip
            num_travelers=2,
            title="Kitesurfing Adventure",
            summary="3 days of wind and waves",
            total_budget_estimate="$2500",
        ),
        "flights": FlightsSection(),
        "accommodations": AccommodationsSection(),
        "logistics": LogisticsSection(),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    if with_activities:
        # 3 days matching the date range
        base_itinerary["activities"] = ActivitiesSection(
            days=[
                ActivityDay(
                    day_number=1,
                    date="2026-03-15",
                    title="Arrival",
                    location="Tarifa",
                    activities=[],
                ),
                ActivityDay(
                    day_number=2,
                    date="2026-03-16",
                    title="First Kite",
                    location="Tarifa",
                    activities=[],
                ),
                ActivityDay(
                    day_number=3,
                    date="2026-03-17",
                    title="Departure",
                    location="Tarifa",
                    activities=[],
                ),
            ]
        )
    else:
        # Empty activities (valid for initial creation)
        base_itinerary["activities"] = ActivitiesSection(days=[])

    return SectionedItinerary(**base_itinerary)


class TestIntentClassification:
    def test_classification_model(self):
        classification = IntentClassification(
            primary_section="flights",
            action_type="search",
            confidence=0.95,
        )
        assert classification.primary_section == "flights"
        assert classification.confidence == 0.95

    def test_classification_with_secondary(self):
        classification = IntentClassification(
            primary_section="activities",
            secondary_sections=["logistics"],
            action_type="update",
            confidence=0.8,
        )
        assert "logistics" in classification.secondary_sections

    def test_low_confidence_clarification(self):
        classification = IntentClassification(
            primary_section="overview",
            action_type="clarify",
            confidence=0.4,
            clarification_needed="Did you want to change dates or destination?",
        )
        assert classification.confidence < 0.7
        assert classification.clarification_needed is not None

    def test_confidence_validation_min(self):
        """Test that confidence must be >= 0."""
        with pytest.raises(ValueError):
            IntentClassification(
                primary_section="flights",
                action_type="search",
                confidence=-0.1,
            )

    def test_confidence_validation_max(self):
        """Test that confidence must be <= 1."""
        with pytest.raises(ValueError):
            IntentClassification(
                primary_section="flights",
                action_type="search",
                confidence=1.5,
            )


class TestValidationResult:
    def test_valid_result(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid
        assert len(result.issues) == 0

    def test_result_with_issues(self):
        issue = ConsistencyIssue(
            issue_type="day_count_mismatch",
            description="Activities has 3 days but trip is 5 days",
            affected_sections=["activities", "overview"],
            severity="warning",
        )
        result = ValidationResult(is_valid=False, issues=[issue])
        assert not result.is_valid
        assert len(result.issues) == 1

    def test_consistency_issue_fields(self):
        issue = ConsistencyIssue(
            issue_type="accommodation_gap",
            description="Only 3 nights booked but need 5",
            affected_sections=["accommodations"],
            suggested_fix="Add accommodation for nights 4 and 5",
            severity="error",
        )
        assert issue.issue_type == "accommodation_gap"
        assert issue.suggested_fix is not None
        assert issue.severity == "error"


class TestOrchestratorConsistencyValidation:
    def test_validates_day_count_mismatch(self):
        """Test that validation catches when activities are empty but expected."""
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary(with_activities=False)

        # Activities is empty but trip is 3 days
        result = orchestrator.validate_consistency(itinerary, ["activities"])

        # Should find day count mismatch (0 days vs 3 expected)
        assert any(
            issue.issue_type == "day_count_mismatch" for issue in result.issues
        )

    def test_validates_day_count_match(self):
        """Test that validation passes when activities match dates."""
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary(with_activities=True)

        # Activities has 3 days matching the trip
        result = orchestrator.validate_consistency(itinerary, ["activities"])

        # Should have no day count issues
        assert not any(
            issue.issue_type == "day_count_mismatch" for issue in result.issues
        )

    def test_validates_accommodation_coverage(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        # No accommodations booked for 2 nights (3-day trip = 2 nights)
        result = orchestrator.validate_consistency(itinerary, ["accommodations"])

        assert any(issue.issue_type == "accommodation_gap" for issue in result.issues)

    def test_no_issues_when_valid(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        # Only check flights section (no date validation there)
        result = orchestrator.validate_consistency(itinerary, ["flights"])

        # Flights section has no specific validation yet
        assert result.is_valid


class TestOrchestratorRelatedSections:
    def test_flights_gets_overview_data(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        related = orchestrator._get_related_sections("flights", itinerary)

        assert "overview" in related
        assert related["overview"]["destination"] == "Tarifa, Spain"

    def test_activities_gets_flight_data(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        related = orchestrator._get_related_sections("activities", itinerary)

        assert "flights" in related

    def test_accommodations_gets_activity_locations(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary(with_activities=True)

        related = orchestrator._get_related_sections("accommodations", itinerary)

        assert "activities" in related
        assert "locations" in related["activities"]
        assert "Tarifa" in related["activities"]["locations"]

    def test_logistics_gets_overview_and_flights(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        related = orchestrator._get_related_sections("logistics", itinerary)

        assert "overview" in related
        assert "flights" in related


class TestOrchestratorConstraints:
    def test_flights_gets_date_constraints(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        constraints = orchestrator._build_constraints("flights", itinerary)

        assert any("2026-03-15" in c for c in constraints)
        assert any("2026-03-17" in c for c in constraints)

    def test_flights_gets_traveler_constraint(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        constraints = orchestrator._build_constraints("flights", itinerary)

        assert any("Travelers: 2" in c for c in constraints)

    def test_activities_gets_flight_constraints_when_booked(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()
        itinerary.flights.selected_outbound_id = "fl-001"

        constraints = orchestrator._build_constraints("activities", itinerary)

        assert any("outbound" in c.lower() for c in constraints)

    def test_activities_no_flight_constraints_when_not_booked(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()
        # No flights selected

        constraints = orchestrator._build_constraints("activities", itinerary)

        # Should have date constraints but not flight booking constraints
        assert any("2026-03-15" in c for c in constraints)
        assert not any("outbound" in c.lower() for c in constraints)

    def test_accommodations_gets_activity_locations(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary(with_activities=True)

        constraints = orchestrator._build_constraints("accommodations", itinerary)

        assert any("Tarifa" in c for c in constraints)


class TestOrchestratorParallelization:
    def test_activities_and_flights_cannot_parallelize(self):
        orchestrator = ItineraryOrchestrator()

        # Activities depends on flights
        assert not orchestrator._can_parallelize(["flights", "activities"])

    def test_logistics_cannot_parallelize_with_anything(self):
        orchestrator = ItineraryOrchestrator()

        # Logistics depends on everything
        assert not orchestrator._can_parallelize(["flights", "logistics"])
        assert not orchestrator._can_parallelize(["accommodations", "logistics"])
        assert not orchestrator._can_parallelize(["activities", "logistics"])

    def test_single_section_can_parallelize(self):
        orchestrator = ItineraryOrchestrator()
        assert orchestrator._can_parallelize(["flights"])
        assert orchestrator._can_parallelize(["accommodations"])
        assert orchestrator._can_parallelize(["activities"])

    def test_flights_alone_can_parallelize(self):
        orchestrator = ItineraryOrchestrator()
        assert orchestrator._can_parallelize(["flights"])


class TestOrchestratorService:
    def test_validate_itinerary_consistency(self):
        itinerary = create_test_itinerary()
        result = validate_itinerary_consistency(itinerary)

        assert "is_valid" in result
        assert "issues" in result

    def test_validate_specific_sections(self):
        itinerary = create_test_itinerary()
        result = validate_itinerary_consistency(itinerary, sections=["flights"])

        assert "is_valid" in result


class TestOrchestratorResultModel:
    def test_orchestrator_result_model(self):
        itinerary = create_test_itinerary()
        validation = ValidationResult(is_valid=True)

        result = OrchestratorResult(
            itinerary=itinerary,
            sections_updated=["flights"],
            agent_responses=[],
            validation_result=validation,
            text_response="Flights updated successfully",
        )

        assert result.sections_updated == ["flights"]
        assert result.text_response == "Flights updated successfully"


@pytest.mark.asyncio
class TestOrchestratorClassification:
    async def test_classify_flights_request(self):
        """Test that flight requests are classified correctly."""
        # Mock the Claude API response
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "classify_intent"
        mock_block.input = {
            "primary_section": "flights",
            "action_type": "search",
            "confidence": 0.95,
        }
        mock_response.content = [mock_block]

        orchestrator = ItineraryOrchestrator()
        orchestrator.client = MagicMock()
        orchestrator.client.messages.create = AsyncMock(return_value=mock_response)

        itinerary = create_test_itinerary()
        classification = await orchestrator.classify_request(
            "Find me some flights to Madrid",
            itinerary,
        )

        assert classification.primary_section == "flights"
        assert classification.confidence > 0.7

    async def test_classify_with_secondary_sections(self):
        """Test classification that affects multiple sections."""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "classify_intent"
        mock_block.input = {
            "primary_section": "activities",
            "secondary_sections": ["logistics"],
            "action_type": "update",
            "confidence": 0.85,
        }
        mock_response.content = [mock_block]

        orchestrator = ItineraryOrchestrator()
        orchestrator.client = MagicMock()
        orchestrator.client.messages.create = AsyncMock(return_value=mock_response)

        itinerary = create_test_itinerary()
        classification = await orchestrator.classify_request(
            "Add a kitesurfing lesson and what gear to bring",
            itinerary,
        )

        assert classification.primary_section == "activities"
        assert "logistics" in classification.secondary_sections

    async def test_classify_ambiguous_request(self):
        """Test handling of ambiguous requests."""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "classify_intent"
        mock_block.input = {
            "primary_section": "overview",
            "action_type": "clarify",
            "confidence": 0.4,
            "clarification_needed": "Did you want to change the dates or the destination?",
        }
        mock_response.content = [mock_block]

        orchestrator = ItineraryOrchestrator()
        orchestrator.client = MagicMock()
        orchestrator.client.messages.create = AsyncMock(return_value=mock_response)

        itinerary = create_test_itinerary()
        classification = await orchestrator.classify_request(
            "change it",
            itinerary,
        )

        assert classification.confidence < 0.7
        assert classification.clarification_needed is not None

    async def test_classify_fallback_on_no_tool_use(self):
        """Test fallback when API doesn't return tool use."""
        mock_response = MagicMock()
        mock_response.content = []  # No content blocks

        orchestrator = ItineraryOrchestrator()
        orchestrator.client = MagicMock()
        orchestrator.client.messages.create = AsyncMock(return_value=mock_response)

        itinerary = create_test_itinerary()
        classification = await orchestrator.classify_request(
            "something",
            itinerary,
        )

        # Should get fallback classification
        assert classification.primary_section == "overview"
        assert classification.action_type == "clarify"
        assert classification.confidence == 0.3


class TestOrchestratorAgentRegistry:
    def test_agents_are_initialized(self):
        orchestrator = ItineraryOrchestrator()

        assert "flights" in orchestrator.agents
        assert "accommodations" in orchestrator.agents
        assert "activities" in orchestrator.agents
        assert "logistics" in orchestrator.agents

    @pytest.mark.asyncio
    async def test_dispatch_to_unknown_section_raises(self):
        orchestrator = ItineraryOrchestrator()
        itinerary = create_test_itinerary()

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.dispatch_to_agent("unknown", "test", itinerary)

        assert "Unknown section" in str(exc_info.value)
