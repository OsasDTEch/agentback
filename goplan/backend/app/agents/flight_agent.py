from pydantic_ai import Agent, RunContext
from typing import Any, List, Dict
from dataclasses import dataclass
import logfire
import sys
from goplan.backend.app.api.flightsearch_api import search_flights

import os
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

provider = GoogleProvider(api_key=os.getenv('GOOGLE_API_KEY'))
model = GoogleModel('gemini-2.5-flash', provider=provider)


@dataclass
class FlightDeps:
    preferred_airlines: List[str]


system_prompt = """
You are a flight specialist in the Goplan AI Travel Planner. 
Your role is to help users find the best flights for their trips using real API results.

When the user provides travel details, you should:
1. Extract the origin, destination, departure date, and return date from their request
2. Use the search_flight tool to get available flights
3. Analyze the results and recommend the best options based on:
   - Price (within budget if specified)
   - Travel time and convenience
   - User preferences for airlines
   - Direct flights preferred unless specified otherwise

Always provide clear reasoning for your recommendations and present the information in a user-friendly format.
"""

flight_agent = Agent(
    model,
    system_prompt=system_prompt,
    deps_type=FlightDeps,
    retries=2
)


@flight_agent.tool
async def search_flight(
        ctx: RunContext[FlightDeps],
        origin: str,
        destination: str,
        depart_date: str,
        return_date: str,
        budget_total: float = None
) -> Dict[str, Any]:
    """
    Search for flights between origin and destination.

    Args:
        origin: Origin city or airport name
        destination: Destination city or airport name
        depart_date: Departure date in YYYY-MM-DD format
        return_date: Return date in YYYY-MM-DD format
        budget_total: Maximum budget for flights (optional)
    """
    try:
        # Call the flight search API
        response = search_flights(
            origin_name=origin,
            destination_name=destination,
            depart_date=depart_date,
            return_date=return_date,
            max_price=budget_total if budget_total else None
        )

        # Check if there's an error in the response
        if "error" in response:
            return {"error": response["error"], "data": []}

        flights = response.get("data", [])

        # Sort flights by preferred airlines if specified
        if ctx.deps.preferred_airlines:  # Fixed: was preferred_airline (singular)
            preferred_set = set(code.upper() for code in ctx.deps.preferred_airlines)

            def has_preferred_airline(flight):
                """Check if flight has any preferred airline"""
                for itinerary in flight.get("itineraries", []):
                    for segment in itinerary.get("segments", []):
                        carrier_code = segment.get("carrierCode", "").upper()
                        if carrier_code in preferred_set:
                            return True
                return False

            # Sort flights - preferred airlines first
            flights.sort(key=lambda f: (0 if has_preferred_airline(f) else 1))

        # Format the response for better readability
        formatted_flights = []
        for flight in flights[:6]:  # Limit to top 6 results
            try:
                price = flight.get("price", {}).get("total", "N/A")
                currency = flight.get("price", {}).get("currency", "USD")

                # Extract outbound and return flight details
                outbound = flight.get("itineraries", [{}])[0]
                return_flight = flight.get("itineraries", [{}])[1] if len(flight.get("itineraries", [])) > 1 else None

                formatted_flight = {
                    "price": f"{price} {currency}",
                    "outbound": format_itinerary(outbound) if outbound else None,
                    "return": format_itinerary(return_flight) if return_flight else None,
                    "raw_data": flight  # Keep original data for detailed processing
                }
                formatted_flights.append(formatted_flight)
            except Exception as e:
                # Skip malformed flight data but log the issue
                print(f"Warning: Could not format flight data: {e}")
                continue

        return {
            "data": formatted_flights,
            "total_results": len(flights),
            "message": f"Found {len(formatted_flights)} flight options"
        }

    except Exception as e:
        return {
            "error": f"Flight search failed: {str(e)}",
            "data": []
        }


def format_itinerary(itinerary):
    """Format itinerary data for better readability"""
    if not itinerary:
        return None

    segments = itinerary.get("segments", [])
    if not segments:
        return None

    first_segment = segments[0]
    last_segment = segments[-1]

    duration = itinerary.get("duration", "N/A")

    return {
        "departure": {
            "airport": first_segment.get("departure", {}).get("iataCode", "N/A"),
            "time": first_segment.get("departure", {}).get("at", "N/A")
        },
        "arrival": {
            "airport": last_segment.get("arrival", {}).get("iataCode", "N/A"),
            "time": last_segment.get("arrival", {}).get("at", "N/A")
        },
        "duration": duration,
        "stops": len(segments) - 1,
        "airlines": list(set(seg.get("carrierCode", "Unknown") for seg in segments))
    }