"""Trip Ninja API service for flight search."""

import os
import logging
from datetime import datetime
from typing import List, Optional
import uuid
import httpx

logger = logging.getLogger(__name__)

from app.schemas.flight import (
    FlightSearchRequest,
    FlightSegmentRequest,
    FlightSearchResponse,
    FlightOption,
    FlightSegmentResult,
    FlightLeg,
)

TRIP_NINJA_URL = "https://api.tripninja.io/v3/get-searches/"
TRIP_NINJA_TOKEN = os.getenv("TRIP_NINJA_AUTH_TOKEN", "")

# Mapping of destination names to IATA codes
# This is a simplified mapping - in production, use a proper airport database
DESTINATION_TO_IATA = {
    "tarifa": "AGP",  # Malaga is closest major airport
    "cape town": "CPT",
    "dakhla": "VIL",
    "fuerteventura": "FUE",
    "sal": "SID",
    "bali": "DPS",
    "queenstown": "ZQN",
    "malaga": "AGP",
    "london": "LON",
    "paris": "PAR",
    "new york": "JFK",
    "nyc": "JFK",
    "los angeles": "LAX",
    "san francisco": "SFO",
    "colombia": "BOG",  # Bogotá El Dorado
    "bogota": "BOG",
    "cartagena": "CTG",
    "medellin": "MDE",
}


def get_iata_code(destination: str) -> Optional[str]:
    """Get IATA code for a destination name."""
    normalized = destination.lower().strip()
    return DESTINATION_TO_IATA.get(normalized)


def build_segments_from_itinerary(
    origin: str,
    destinations: List[str],
    dates: List[str],
    cabin_class: str = "E",
) -> List[FlightSegmentRequest]:
    """
    Build flight segments from itinerary data.

    Args:
        origin: Starting point (city name or IATA code)
        destinations: List of destinations in order
        dates: List of travel dates (YYYY-MM-DD) for each segment
        cabin_class: E=economy, B=business, F=first

    Returns:
        List of FlightSegmentRequest objects
    """
    segments = []

    # Get IATA codes
    origin_iata = get_iata_code(origin) or origin.upper()

    all_points = [origin] + destinations
    for i, (date, dest) in enumerate(zip(dates, destinations)):
        from_point = all_points[i]
        to_point = dest

        from_iata = get_iata_code(from_point) or from_point.upper()
        to_iata = get_iata_code(to_point) or to_point.upper()

        segments.append(
            FlightSegmentRequest(
                id=i + 1,
                departure_date=date,
                cabin_class=cabin_class,
                from_iata=from_iata,
                to_iata=to_iata,
                from_type="C",
                to_type="C",
            )
        )

    return segments


async def search_flights(
    request: FlightSearchRequest,
) -> FlightSearchResponse:
    """
    Search for flights using Trip Ninja API.

    Args:
        request: Flight search request with segments

    Returns:
        FlightSearchResponse with options
    """
    search_id = str(uuid.uuid4())
    searched_at = datetime.utcnow()

    # Build the API request
    api_request = {
        "segments": [
            {
                "id": seg.id,
                "departure_date": seg.departure_date,
                "cabin_class": seg.cabin_class,
                "from_iata": seg.from_iata,
                "to_iata": seg.to_iata,
                "from_type": seg.from_type,
                "to_type": seg.to_type,
            }
            for seg in request.segments
        ],
        "travellers": request.travellers,
        "currency": request.currency,
        "country_code": "US",
        "cabin_class": request.segments[0].cabin_class if request.segments else "E",
        "time_value": 40,
        "num_results": 500,
        "markup_source": "onsite",
        "return_single_pnr_itineraries": True,
        "single_pnr": True,
        "virtual_interlining": request.virtual_interlining,
    }

    headers = {
        "Authorization": f"Basic {TRIP_NINJA_TOKEN}",
        "Content-Type": "application/json",
        "coast-demo": "allow",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\n{'='*80}")
            print(f"[FLIGHT_SERVICE] Calling Trip Ninja API: {TRIP_NINJA_URL}")
            print(f"[FLIGHT_SERVICE] Request payload:")
            import json
            print(json.dumps(api_request, indent=2))
            print(f"[FLIGHT_SERVICE] Headers: {headers}")
            print(f"{'='*80}\n")
            response = await client.post(
                TRIP_NINJA_URL,
                json=api_request,
                headers=headers,
            )
            print(f"[FLIGHT_SERVICE] Trip Ninja response status: {response.status_code}")
            print(f"[FLIGHT_SERVICE] Trip Ninja full response: {response.text}")
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            # Return empty results on API error
            logger.error(f"Trip Ninja HTTP error: {e.response.status_code} - {e.response.text}")
            return FlightSearchResponse(
                search_id=search_id,
                searched_at=searched_at,
                origin=request.segments[0].from_iata if request.segments else "",
                destination=request.segments[-1].to_iata if request.segments else "",
                options=[],
                cheapest_price=None,
                price_range=None,
            )
        except Exception as e:
            logger.error(f"Trip Ninja API error: {str(e)}")
            return FlightSearchResponse(
                search_id=search_id,
                searched_at=searched_at,
                origin=request.segments[0].from_iata if request.segments else "",
                destination=request.segments[-1].to_iata if request.segments else "",
                options=[],
                cheapest_price=None,
                price_range=None,
            )

    # Parse the response
    print(f"[FLIGHT_SERVICE] Response data keys: {data.keys()}")
    print(f"[FLIGHT_SERVICE] Has 'results' key: {'results' in data}")
    print(f"[FLIGHT_SERVICE] Has 'trip_id' key: {'trip_id' in data}")

    # If we got a trip_id, we need to poll for results
    if "trip_id" in data and "results" not in data:
        trip_id = data["trip_id"]
        print(f"[FLIGHT_SERVICE] Got trip_id, polling for results...")

        # Poll for results (try up to 10 times, 1 second apart)
        import asyncio
        for attempt in range(10):
            await asyncio.sleep(1)

            poll_response = await client.get(
                f"{TRIP_NINJA_URL}{trip_id}/",
                headers=headers,
            )

            if poll_response.status_code == 200:
                poll_data = poll_response.json()
                print(f"[FLIGHT_SERVICE] Poll attempt {attempt + 1}: {list(poll_data.keys())}")

                if "results" in poll_data:
                    print(f"[FLIGHT_SERVICE] Got results! {len(poll_data.get('results', []))} options")
                    data = poll_data
                    break
        else:
            print(f"[FLIGHT_SERVICE] Polling timeout - no results after 10 attempts")

    options = []
    results = data.get("results", [])

    for i, result in enumerate(results[:10]):  # Limit to 10 options
        segments_result = []
        for seg_data in result.get("segments", []):
            flights = []
            for flight_data in seg_data.get("flights", []):
                flights.append(
                    FlightLeg(
                        departure_airport=flight_data.get("departure_airport", ""),
                        arrival_airport=flight_data.get("arrival_airport", ""),
                        departure_time=flight_data.get("departure_time", ""),
                        arrival_time=flight_data.get("arrival_time", ""),
                        airline=flight_data.get("airline", ""),
                        flight_number=flight_data.get("flight_number", ""),
                        duration_minutes=flight_data.get("duration_minutes", 0),
                        operating_airline=flight_data.get("operating_airline"),
                    )
                )
            segments_result.append(
                FlightSegmentResult(
                    segment_id=seg_data.get("segment_id", i + 1),
                    flights=flights,
                )
            )

        total_price = result.get("total_price", 0)
        num_travelers = len(request.travellers)

        options.append(
            FlightOption(
                id=result.get("id", f"option-{i + 1}"),
                total_price=total_price,
                currency=request.currency,
                price_per_person=total_price / num_travelers
                if num_travelers > 0
                else total_price,
                segments=segments_result,
                is_virtual_interlining=result.get("is_virtual_interlining", False),
                warnings=result.get("warnings", []),
                booking_url=result.get("booking_url"),
            )
        )

    # Calculate price range
    cheapest = min((o.total_price for o in options), default=None)
    most_expensive = max((o.total_price for o in options), default=None)
    price_range = None
    if cheapest is not None and most_expensive is not None:
        price_range = f"${cheapest:.0f}-${most_expensive:.0f}"

    return FlightSearchResponse(
        search_id=search_id,
        searched_at=searched_at,
        origin=request.segments[0].from_iata if request.segments else "",
        destination=request.segments[-1].to_iata if request.segments else "",
        options=options,
        cheapest_price=cheapest,
        price_range=price_range,
    )
