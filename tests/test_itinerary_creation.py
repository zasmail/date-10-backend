"""Tests for itinerary creation functionality."""

import pytest
import json
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models import Itinerary, Conversation
from app.schemas.itinerary import ItineraryData, ItineraryProposal, ItineraryDay, Activity


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


class TestItineraryDataValidation:
    """Test itinerary data schema validation."""

    def test_single_proposal_valid(self):
        """Single proposal should pass validation."""
        data = {
            "destination": "Chile",
            "start_date": "2026-02-11",
            "end_date": "2026-02-23",
            "num_travelers": 2,
            "proposals": [
                {
                    "id": "prop-1",
                    "title": "Chilean Adventure",
                    "summary": "Explore diverse landscapes",
                    "days": [
                        {
                            "day_number": 1,
                            "date": "2026-02-11",
                            "title": "Arrival in Santiago",
                            "location": "Santiago",
                            "activities": [
                                {
                                    "time": "14:00",
                                    "name": "Airport arrival",
                                    "description": "Transfer to hotel",
                                    "duration": "1 hour",
                                }
                            ],
                        }
                    ],
                    "total_budget_estimate": "$2500-3000",
                    "highlights": ["Santiago exploration"],
                    "caveats": ["Weather dependent"],
                }
            ],
        }

        itinerary = ItineraryData(**data)
        assert itinerary.destination == "Chile"
        assert len(itinerary.proposals) == 1
        assert itinerary.proposals[0].title == "Chilean Adventure"

    def test_multiple_proposals_valid(self):
        """Multiple proposals should still work."""
        data = {
            "destination": "Chile",
            "start_date": "2026-02-11",
            "end_date": "2026-02-23",
            "proposals": [
                {
                    "id": "prop-1",
                    "title": "Adventure",
                    "summary": "Exciting",
                    "days": [],
                    "total_budget_estimate": "$2500",
                    "highlights": [],
                    "caveats": [],
                },
                {
                    "id": "prop-2",
                    "title": "Relaxed",
                    "summary": "Chill",
                    "days": [],
                    "total_budget_estimate": "$2000",
                    "highlights": [],
                    "caveats": [],
                },
            ],
        }

        itinerary = ItineraryData(**data)
        assert len(itinerary.proposals) == 2

    def test_empty_proposals_invalid(self):
        """Empty proposals list should fail validation."""
        data = {
            "destination": "Chile",
            "start_date": "2026-02-11",
            "end_date": "2026-02-23",
            "proposals": [],
        }

        with pytest.raises(Exception):  # Pydantic ValidationError
            ItineraryData(**data)

    def test_missing_required_fields_invalid(self):
        """Missing required fields should fail validation."""
        data = {
            "destination": "Chile",
            # Missing start_date, end_date
            "proposals": [
                {
                    "id": "prop-1",
                    "title": "Adventure",
                    "summary": "Exciting",
                    "days": [],
                    "total_budget_estimate": "$2500",
                    "highlights": [],
                    "caveats": [],
                }
            ],
        }

        with pytest.raises(Exception):  # Pydantic ValidationError
            ItineraryData(**data)

    def test_activity_validation(self):
        """Test activity schema validation."""
        activity_data = {
            "time": "14:00",
            "name": "City tour",
            "description": "Explore Santiago",
            "duration": "3 hours",
            "location": "Downtown Santiago",
            "cost_estimate": "$50",
            "booking_required": True,
        }

        activity = Activity(**activity_data)
        assert activity.time == "14:00"
        assert activity.booking_required is True

    def test_day_validation(self):
        """Test day schema validation."""
        day_data = {
            "day_number": 1,
            "date": "2026-02-11",
            "title": "Arrival",
            "location": "Santiago",
            "activities": [
                {
                    "time": "14:00",
                    "name": "Airport pickup",
                    "description": "Transfer",
                    "duration": "1 hour",
                }
            ],
        }

        day = ItineraryDay(**day_data)
        assert day.day_number == 1
        assert len(day.activities) == 1


class TestItineraryDatabaseOperations:
    """Test itinerary database operations."""

    def test_create_itinerary(self, session: Session):
        """Test creating an itinerary in the database."""
        proposals = [
            {
                "id": "prop-1",
                "title": "Adventure",
                "summary": "Action-packed",
                "days": [],
                "total_budget_estimate": "$1500",
                "highlights": ["Surfing"],
                "caveats": ["Weather"],
            }
        ]

        itinerary = Itinerary(
            destination="Chile",
            start_date="2026-02-11",
            end_date="2026-02-23",
            proposals_json=json.dumps(proposals),
        )
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)

        assert itinerary.id is not None
        assert itinerary.destination == "Chile"

        # Verify it's in the database
        retrieved = session.exec(select(Itinerary)).first()
        assert retrieved is not None
        assert retrieved.destination == "Chile"

    def test_itinerary_with_conversation(self, session: Session):
        """Test linking itinerary to conversation."""
        # Create conversation
        conversation = Conversation()
        session.add(conversation)
        session.commit()
        session.refresh(conversation)

        # Create itinerary linked to conversation
        proposals = [
            {
                "id": "prop-1",
                "title": "Adventure",
                "summary": "Exciting",
                "days": [],
                "total_budget_estimate": "$2500",
                "highlights": [],
                "caveats": [],
            }
        ]

        itinerary = Itinerary(
            destination="Chile",
            start_date="2026-02-11",
            end_date="2026-02-23",
            proposals_json=json.dumps(proposals),
            conversation_id=str(conversation.id),
        )
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)

        assert itinerary.conversation_id == str(conversation.id)

        # Query itineraries for this conversation
        itineraries = session.exec(
            select(Itinerary).where(Itinerary.conversation_id == str(conversation.id))
        ).all()
        assert len(itineraries) == 1

    def test_multiple_itineraries_same_conversation(self, session: Session):
        """Test multiple itineraries in same conversation."""
        conversation = Conversation()
        session.add(conversation)
        session.commit()
        session.refresh(conversation)

        proposals = [
            {
                "id": "prop-1",
                "title": "Option",
                "summary": "Summary",
                "days": [],
                "total_budget_estimate": "$2000",
                "highlights": [],
                "caveats": [],
            }
        ]

        # Create two itineraries
        for dest in ["Chile", "Peru"]:
            itinerary = Itinerary(
                destination=dest,
                start_date="2026-02-11",
                end_date="2026-02-23",
                proposals_json=json.dumps(proposals),
                conversation_id=str(conversation.id),
            )
            session.add(itinerary)
        session.commit()

        # Query both
        itineraries = session.exec(
            select(Itinerary).where(Itinerary.conversation_id == str(conversation.id))
        ).all()
        assert len(itineraries) == 2


class TestProposalConversion:
    """Test proposal conversion from single to array format."""

    def test_single_proposal_wrapper(self):
        """Test wrapping single proposal in array."""
        tool_input = {
            "destination": "Chile",
            "start_date": "2026-02-11",
            "end_date": "2026-02-23",
            "proposal": {
                "id": "prop-1",
                "title": "Adventure",
                "summary": "Fun",
                "days": [],
                "total_budget_estimate": "$2500",
                "highlights": [],
                "caveats": [],
            },
        }

        # Simulate conversion logic from claude_service.py
        proposal = tool_input.get("proposal")
        tool_input["proposals"] = [proposal] if proposal else []
        del tool_input["proposal"]

        # Verify structure
        assert "proposals" in tool_input
        assert "proposal" not in tool_input
        assert len(tool_input["proposals"]) == 1

        # Verify validation passes
        itinerary = ItineraryData(**tool_input)
        assert len(itinerary.proposals) == 1

    def test_proposal_id_generation(self):
        """Test ID generation for proposals without ID."""
        import uuid

        tool_input = {
            "destination": "Chile",
            "start_date": "2026-02-11",
            "end_date": "2026-02-23",
            "proposal": {
                # Missing id
                "title": "Adventure",
                "summary": "Fun",
                "days": [],
                "total_budget_estimate": "$2500",
                "highlights": [],
                "caveats": [],
            },
        }

        # Simulate ID generation
        proposal = tool_input.get("proposal")
        if proposal and "id" not in proposal:
            proposal["id"] = str(uuid.uuid4())

        # Verify ID was added
        assert "id" in tool_input["proposal"]
        assert len(tool_input["proposal"]["id"]) == 36  # UUID length

        # Verify it's a valid UUID
        try:
            uuid.UUID(tool_input["proposal"]["id"])
        except ValueError:
            pytest.fail("Generated ID is not a valid UUID")


class TestErrorConditions:
    """Test error handling conditions."""

    def test_invalid_date_format(self):
        """Test handling of invalid date formats."""
        data = {
            "destination": "Chile",
            "start_date": "not-a-date",
            "end_date": "2026-02-23",
            "proposals": [
                {
                    "id": "prop-1",
                    "title": "Adventure",
                    "summary": "Exciting",
                    "days": [],
                    "total_budget_estimate": "$2500",
                    "highlights": [],
                    "caveats": [],
                }
            ],
        }

        # Should still accept it (basic string validation)
        itinerary = ItineraryData(**data)
        assert itinerary.start_date == "not-a-date"

    def test_negative_num_travelers(self):
        """Test validation rejects negative num_travelers."""
        data = {
            "destination": "Chile",
            "start_date": "2026-02-11",
            "end_date": "2026-02-23",
            "num_travelers": -1,
            "proposals": [
                {
                    "id": "prop-1",
                    "title": "Adventure",
                    "summary": "Exciting",
                    "days": [],
                    "total_budget_estimate": "$2500",
                    "highlights": [],
                    "caveats": [],
                }
            ],
        }

        # Should reject negative travelers
        with pytest.raises(Exception):  # Pydantic ValidationError
            ItineraryData(**data)

    def test_proposal_without_days(self):
        """Test proposal with empty days list."""
        data = {
            "destination": "Chile",
            "start_date": "2026-02-11",
            "end_date": "2026-02-23",
            "proposals": [
                {
                    "id": "prop-1",
                    "title": "Minimal",
                    "summary": "Just a summary",
                    "days": [],  # Empty days list
                    "total_budget_estimate": "$2500",
                    "highlights": [],
                    "caveats": [],
                }
            ],
        }

        # Should be valid
        itinerary = ItineraryData(**data)
        assert len(itinerary.proposals[0].days) == 0
