"""Tests for sectioned itinerary schemas.

This test suite validates all section schemas, their validators,
the SectionedItinerary model, and the migration utility.
"""

import pytest
from datetime import datetime
import uuid

from app.schemas.itinerary_sections import (
    OverviewSection,
    FlightsSection,
    FlightOption,
    AccommodationsSection,
    AccommodationNight,
    ActivitiesSection,
    ActivityDay,
    ActivityItem,
    LogisticsSection,
    SectionedItinerary,
)
from app.models.sectioned_itinerary import (
    SectionedItineraryModel,
    migrate_proposal_to_sections,
)


class TestOverviewSection:
    """Tests for OverviewSection schema."""

    def test_valid_overview(self):
        """Test creating a valid overview section."""
        overview = OverviewSection(
            destination="Tarifa, Spain",
            start_date="2026-03-15",
            end_date="2026-03-20",
            num_travelers=2,
            title="Kitesurfing Adventure",
            summary="5 days of wind and waves in Spain's kite capital",
            total_budget_estimate="$2000-2500",
        )
        assert overview.destination == "Tarifa, Spain"
        assert overview.num_travelers == 2
        assert overview.title == "Kitesurfing Adventure"

    def test_overview_with_highlights(self):
        """Test overview with highlights list."""
        overview = OverviewSection(
            destination="Bali",
            start_date="2026-04-01",
            end_date="2026-04-10",
            title="Surf & Culture",
            summary="Explore Bali's waves and temples",
            total_budget_estimate="$3000",
            highlights=["World-class surf", "Ancient temples", "Rice terraces"],
        )
        assert len(overview.highlights) == 3
        assert "World-class surf" in overview.highlights

    def test_overview_default_values(self):
        """Test default values are applied."""
        overview = OverviewSection(
            destination="Morocco",
            start_date="2026-05-01",
            end_date="2026-05-07",
            title="Desert Adventure",
            summary="Trek through the Sahara",
            total_budget_estimate="$1500",
        )
        assert overview.num_travelers == 1
        assert overview.highlights == []
        assert overview.notes == ""

    def test_end_date_before_start_date_fails(self):
        """Test that end_date before start_date raises validation error."""
        with pytest.raises(ValueError, match="must be >= start_date"):
            OverviewSection(
                destination="Invalid",
                start_date="2026-03-20",
                end_date="2026-03-15",  # Before start
                title="Test",
                summary="Test",
                total_budget_estimate="$100",
            )

    def test_invalid_date_format_fails(self):
        """Test that invalid date format raises validation error."""
        with pytest.raises(ValueError, match="must be in YYYY-MM-DD format"):
            OverviewSection(
                destination="Test",
                start_date="03-15-2026",  # Wrong format
                end_date="2026-03-20",
                title="Test",
                summary="Test",
                total_budget_estimate="$100",
            )


class TestFlightsSection:
    """Tests for FlightsSection schema."""

    def test_empty_flights_section(self):
        """Test creating an empty flights section."""
        flights = FlightsSection()
        assert flights.outbound_flights == []
        assert flights.return_flights == []
        assert flights.selected_outbound_id is None
        assert flights.selected_return_id is None
        assert flights.search_params is None

    def test_with_flight_options(self):
        """Test flights section with options."""
        option = FlightOption(
            id="fl-001",
            airline="Iberia",
            departure_airport="JFK",
            arrival_airport="MAD",
            departure_time="2026-03-15T10:00:00",
            arrival_time="2026-03-15T22:00:00",
            duration="7h 00m",
            price="$650",
        )
        flights = FlightsSection(
            outbound_flights=[option],
            selected_outbound_id="fl-001",
        )
        assert len(flights.outbound_flights) == 1
        assert flights.selected_outbound_id == "fl-001"
        assert flights.outbound_flights[0].airline == "Iberia"

    def test_flight_with_segments(self):
        """Test flight option with multiple segments."""
        option = FlightOption(
            id="fl-002",
            airline="United",
            departure_airport="SFO",
            arrival_airport="BCN",
            departure_time="2026-03-15T08:00:00",
            arrival_time="2026-03-16T06:00:00",
            duration="13h 00m",
            price="$890",
            segments=[
                {"from": "SFO", "to": "EWR", "duration": "5h 30m"},
                {"from": "EWR", "to": "BCN", "duration": "7h 30m"},
            ],
            booking_link="https://example.com/book",
        )
        assert len(option.segments) == 2
        assert option.booking_link == "https://example.com/book"

    def test_flights_with_search_params(self):
        """Test flights section with search parameters."""
        flights = FlightsSection(
            search_params={
                "origin": "JFK",
                "destination": "AGP",
                "departure_date": "2026-03-15",
                "return_date": "2026-03-20",
                "cabin_class": "economy",
            }
        )
        assert flights.search_params["origin"] == "JFK"


class TestAccommodationsSection:
    """Tests for AccommodationsSection schema."""

    def test_empty_accommodations(self):
        """Test empty accommodations section."""
        section = AccommodationsSection()
        assert section.nights == []
        assert section.total_accommodation_cost is None

    def test_accommodation_nights(self):
        """Test accommodations with multiple nights."""
        night = AccommodationNight(
            date="2026-03-15",
            name="Casa del Surf",
            area="Tarifa Old Town",
            style="Boutique surf hotel",
            price_range="$120-150/night",
        )
        section = AccommodationsSection(nights=[night])
        assert len(section.nights) == 1
        assert section.nights[0].name == "Casa del Surf"
        assert section.nights[0].area == "Tarifa Old Town"

    def test_accommodation_with_total_cost(self):
        """Test accommodations with total cost estimate."""
        nights = [
            AccommodationNight(
                date="2026-03-15",
                name="Hotel Day 1",
                area="Beach",
                style="Resort",
                price_range="$200/night",
            ),
            AccommodationNight(
                date="2026-03-16",
                name="Hotel Day 2",
                area="Beach",
                style="Resort",
                price_range="$200/night",
            ),
        ]
        section = AccommodationsSection(
            nights=nights,
            total_accommodation_cost="$400-500",
        )
        assert len(section.nights) == 2
        assert section.total_accommodation_cost == "$400-500"

    def test_accommodation_invalid_date_fails(self):
        """Test that invalid date format raises error."""
        with pytest.raises(ValueError, match="must be in YYYY-MM-DD format"):
            AccommodationNight(
                date="March 15, 2026",  # Wrong format
                name="Test",
                area="Test",
                style="Test",
                price_range="$100",
            )


class TestActivitiesSection:
    """Tests for ActivitiesSection schema."""

    def test_empty_activities(self):
        """Test empty activities section."""
        section = ActivitiesSection()
        assert section.days == []
        assert section.total_activities_cost is None

    def test_activity_days(self):
        """Test activities with day structure."""
        activity = ActivityItem(
            time="09:00",
            name="Kitesurfing lesson",
            description="Beginner lesson at Los Lances beach",
            duration="3 hours",
            cost_estimate="$80",
            booking_required=True,
        )
        day = ActivityDay(
            day_number=1,
            date="2026-03-15",
            title="Arrival & First Kite",
            location="Tarifa",
            activities=[activity],
        )
        section = ActivitiesSection(days=[day])
        assert len(section.days) == 1
        assert section.days[0].activities[0].booking_required is True

    def test_activity_with_operator(self):
        """Test activity with local operator."""
        activity = ActivityItem(
            time="10:00",
            name="Guided surf session",
            description="Morning surf with local guide",
            duration="2 hours",
            operator="Tarifa Kite School",
        )
        assert activity.operator == "Tarifa Kite School"

    def test_multiple_activities_per_day(self):
        """Test day with multiple activities."""
        activities = [
            ActivityItem(
                time="09:00",
                name="Morning surf",
                description="Early session",
                duration="2 hours",
            ),
            ActivityItem(
                time="12:00",
                name="Lunch",
                description="Seafood at the port",
                duration="1 hour",
            ),
            ActivityItem(
                time="15:00",
                name="Afternoon kite",
                description="Wind usually picks up",
                duration="3 hours",
            ),
        ]
        day = ActivityDay(
            day_number=1,
            date="2026-03-15",
            title="Full Day of Action",
            location="Tarifa",
            activities=activities,
        )
        assert len(day.activities) == 3

    def test_activity_day_invalid_date_fails(self):
        """Test that invalid date format raises error."""
        with pytest.raises(ValueError, match="must be in YYYY-MM-DD format"):
            ActivityDay(
                day_number=1,
                date="2026/03/15",  # Wrong format
                title="Test",
                location="Test",
            )


class TestLogisticsSection:
    """Tests for LogisticsSection schema."""

    def test_empty_logistics(self):
        """Test empty logistics section."""
        logistics = LogisticsSection()
        assert logistics.transportation_notes == []
        assert logistics.packing_suggestions == []
        assert logistics.caveats == []
        assert logistics.visa_requirements is None

    def test_logistics_with_caveats(self):
        """Test logistics with various fields."""
        logistics = LogisticsSection(
            transportation_notes=["Rent a car at Jerez airport"],
            packing_suggestions=["Wetsuit", "Sunscreen", "Reef-safe sunblock"],
            caveats=["Wind conditions vary - have backup plan"],
        )
        assert len(logistics.caveats) == 1
        assert len(logistics.packing_suggestions) == 3

    def test_logistics_with_visa_info(self):
        """Test logistics with visa requirements."""
        logistics = LogisticsSection(
            visa_requirements="US citizens: 90 days visa-free in Schengen",
            health_notes=["No special vaccinations required"],
        )
        assert "90 days" in logistics.visa_requirements
        assert len(logistics.health_notes) == 1


class TestSectionedItinerary:
    """Tests for the complete SectionedItinerary model."""

    def test_full_sectioned_itinerary(self):
        """Test creating a complete sectioned itinerary."""
        itinerary = SectionedItinerary(
            id=str(uuid.uuid4()),
            overview=OverviewSection(
                destination="Tarifa",
                start_date="2026-03-15",
                end_date="2026-03-20",
                title="Kite Trip",
                summary="Adventure awaits in Tarifa",
                total_budget_estimate="$2500",
            ),
            flights=FlightsSection(),
            accommodations=AccommodationsSection(),
            activities=ActivitiesSection(),
            logistics=LogisticsSection(),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        assert itinerary.overview.destination == "Tarifa"
        assert itinerary.version == 1

    def test_itinerary_with_activities_matching_dates(self):
        """Test itinerary where activity days match date range."""
        # 3-day trip (15th, 16th, 17th = 3 days)
        days = [
            ActivityDay(
                day_number=i + 1,
                date=f"2026-03-{15 + i}",
                title=f"Day {i + 1}",
                location="Tarifa",
            )
            for i in range(3)
        ]
        itinerary = SectionedItinerary(
            id="test-001",
            overview=OverviewSection(
                destination="Tarifa",
                start_date="2026-03-15",
                end_date="2026-03-17",  # 3 days
                title="Test",
                summary="Test",
                total_budget_estimate="$1000",
            ),
            activities=ActivitiesSection(days=days),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        assert len(itinerary.activities.days) == 3

    def test_itinerary_with_mismatched_days_fails(self):
        """Test that mismatched activity days count raises error."""
        days = [
            ActivityDay(
                day_number=1,
                date="2026-03-15",
                title="Day 1",
                location="Tarifa",
            ),
            ActivityDay(
                day_number=2,
                date="2026-03-16",
                title="Day 2",
                location="Tarifa",
            ),
        ]
        with pytest.raises(ValueError, match="doesn't match date range"):
            SectionedItinerary(
                id="test-fail",
                overview=OverviewSection(
                    destination="Tarifa",
                    start_date="2026-03-15",
                    end_date="2026-03-20",  # 6 days but only 2 activity days
                    title="Test",
                    summary="Test",
                    total_budget_estimate="$1000",
                ),
                activities=ActivitiesSection(days=days),
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )

    def test_itinerary_empty_activities_valid(self):
        """Test that empty activities is valid (for initial creation)."""
        itinerary = SectionedItinerary(
            id="test-empty",
            overview=OverviewSection(
                destination="Tarifa",
                start_date="2026-03-15",
                end_date="2026-03-20",
                title="Test",
                summary="Test",
                total_budget_estimate="$1000",
            ),
            activities=ActivitiesSection(),  # Empty
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        assert len(itinerary.activities.days) == 0


class TestMigration:
    """Tests for the migration utility."""

    def test_migrate_proposal_to_sections(self):
        """Test converting legacy ItineraryProposal to SectionedItinerary."""
        legacy_proposal = {
            "id": "prop-001",
            "title": "Adventure Focus",
            "summary": "An action-packed trip to Spain's kite capital",
            "total_budget_estimate": "$2000-2500",
            "highlights": ["Kitesurfing", "Old town exploration"],
            "caveats": ["Weather dependent", "Book kite lessons early"],
            "days": [
                {
                    "day_number": 1,
                    "date": "2026-03-15",
                    "title": "Arrival",
                    "location": "Tarifa",
                    "activities": [
                        {
                            "time": "14:00",
                            "name": "Check in",
                            "description": "Arrive and settle in",
                            "duration": "1 hour",
                        }
                    ],
                    "accommodation": {
                        "name": "Hotel Arte Vida",
                        "area": "Beach",
                        "style": "Boutique",
                        "price_range": "$150/night",
                    },
                }
            ],
        }

        sectioned = migrate_proposal_to_sections(
            proposal=legacy_proposal,
            destination="Tarifa, Spain",
            start_date="2026-03-15",
            end_date="2026-03-15",  # Single day to match
            num_travelers=2,
        )

        assert sectioned.overview.destination == "Tarifa, Spain"
        assert sectioned.overview.title == "Adventure Focus"
        assert sectioned.overview.num_travelers == 2
        assert len(sectioned.activities.days) == 1
        assert len(sectioned.accommodations.nights) == 1
        assert sectioned.logistics.caveats == [
            "Weather dependent",
            "Book kite lessons early",
        ]

    def test_migrate_proposal_without_accommodation(self):
        """Test migration when day has no accommodation."""
        legacy_proposal = {
            "id": "prop-002",
            "title": "Day Trip",
            "summary": "Quick adventure",
            "total_budget_estimate": "$500",
            "days": [
                {
                    "day_number": 1,
                    "date": "2026-03-15",
                    "title": "Day Trip",
                    "location": "Tarifa",
                    "activities": [
                        {
                            "time": "10:00",
                            "name": "Explore",
                            "description": "Walking tour",
                            "duration": "3 hours",
                        }
                    ],
                    # No accommodation
                }
            ],
        }

        sectioned = migrate_proposal_to_sections(
            proposal=legacy_proposal,
            destination="Tarifa",
            start_date="2026-03-15",
            end_date="2026-03-15",
        )

        assert len(sectioned.accommodations.nights) == 0
        assert len(sectioned.activities.days) == 1

    def test_migrate_proposal_preserves_id(self):
        """Test that migration preserves the proposal ID."""
        legacy_proposal = {
            "id": "preserve-me-123",
            "title": "Test",
            "summary": "Test",
            "total_budget_estimate": "$100",
            "days": [],
        }

        sectioned = migrate_proposal_to_sections(
            proposal=legacy_proposal,
            destination="Test",
            start_date="2026-03-15",
            end_date="2026-03-15",
        )

        assert sectioned.id == "preserve-me-123"


class TestSectionedItineraryModel:
    """Tests for the SQLModel persistence model."""

    def test_model_json_serialization(self):
        """Test that sections serialize and deserialize correctly."""
        itinerary = SectionedItinerary(
            id="test-001",
            overview=OverviewSection(
                destination="Tarifa",
                start_date="2026-03-15",
                end_date="2026-03-20",
                title="Test Trip",
                summary="Test summary",
                total_budget_estimate="$1000",
            ),
            flights=FlightsSection(),
            accommodations=AccommodationsSection(),
            activities=ActivitiesSection(),
            logistics=LogisticsSection(),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

        # Serialize
        json_str = itinerary.model_dump_json()

        # Deserialize
        restored = SectionedItinerary.model_validate_json(json_str)

        assert restored.id == "test-001"
        assert restored.overview.destination == "Tarifa"
        assert restored.overview.title == "Test Trip"

    def test_model_from_sections_factory(self):
        """Test creating model from sections using factory method."""
        sections = SectionedItinerary(
            id="factory-test",
            overview=OverviewSection(
                destination="Morocco",
                start_date="2026-04-01",
                end_date="2026-04-07",
                title="Desert Trek",
                summary="Sahara adventure",
                total_budget_estimate="$2000",
            ),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

        model = SectionedItineraryModel.from_sections(
            sections=sections,
            conversation_id="conv-123",
            user_id="user-456",
        )

        assert model.id == "factory-test"
        assert model.destination == "Morocco"
        assert model.conversation_id == "conv-123"
        assert model.user_id == "user-456"

    def test_model_sections_property_roundtrip(self):
        """Test sections property getter and setter."""
        sections = SectionedItinerary(
            id="roundtrip-test",
            overview=OverviewSection(
                destination="Bali",
                start_date="2026-05-01",
                end_date="2026-05-10",
                title="Surf Paradise",
                summary="Waves and culture",
                total_budget_estimate="$3000",
            ),
            flights=FlightsSection(
                outbound_flights=[
                    FlightOption(
                        id="fl-test",
                        airline="Qatar",
                        departure_airport="SFO",
                        arrival_airport="DPS",
                        departure_time="2026-05-01T00:00:00",
                        arrival_time="2026-05-02T12:00:00",
                        duration="24h",
                        price="$1200",
                    )
                ]
            ),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

        model = SectionedItineraryModel.from_sections(sections)

        # Access through property
        retrieved = model.sections
        assert retrieved.overview.destination == "Bali"
        assert len(retrieved.flights.outbound_flights) == 1
        assert retrieved.flights.outbound_flights[0].airline == "Qatar"


class TestSectionUpdate:
    """Tests for updating individual sections."""

    def test_update_single_section(self):
        """Test updating a single section via model method."""
        sections = SectionedItinerary(
            id="update-test",
            overview=OverviewSection(
                destination="Tarifa",
                start_date="2026-03-15",
                end_date="2026-03-20",
                title="Original Title",
                summary="Original summary",
                total_budget_estimate="$1000",
            ),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

        model = SectionedItineraryModel.from_sections(sections)
        original_version = model.version

        # Update just the logistics section
        model.update_section(
            "logistics",
            {
                "transportation_notes": ["New transport note"],
                "packing_suggestions": ["New item"],
                "booking_requirements": [],
                "visa_requirements": None,
                "health_notes": [],
                "caveats": ["New caveat"],
            },
        )

        # Version should have bumped
        assert model.version == original_version + 1

        # Retrieve and verify
        updated_sections = model.sections
        assert updated_sections.logistics.transportation_notes == ["New transport note"]
        assert updated_sections.logistics.caveats == ["New caveat"]
        # Overview should be unchanged
        assert updated_sections.overview.title == "Original Title"
