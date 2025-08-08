from pydantic_ai import Agent, RunContext
from typing import Any, List, Dict
from dataclasses import dataclass
import os

from goplan.backend.app.api.flightsearch_api import search_flights  # Now using aviationstack-based function
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

# Google model setup
provider = GoogleProvider(api_key=os.getenv('GOOGLE_API_KEY'))
model = GoogleModel('gemini-2.5-flash', provider=provider)


@dataclass
class FlightDeps:
    preferred_airlines: List[str]


system_prompt = """
You are a flight specialist in the Goplan AI Travel Planner.
You use real-time aviation data to help users find available flights between locations.
Only provide real results — do not make up flights or prices.

Given a user’s request:
1. Extract origin, destination, and departure date
2. Use the search_flight tool to get available flights
3. Recommend the best options based on:
   - Airline preferences
   - Direct flights
   - Flight time and convenience

Avoid showing unavailable flights or fake prices. Return top 3–6 real flights found.
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
    return_date: str = None,
    budget_total: float = None
) -> Dict[str, Any]:
    """
    Search for flights using Aviationstack.

    Args:
        origin: IATA code of origin airport (e.g. 'JFK')
        destination: IATA code of destination airport (e.g. 'LHR')
        depart_date: Departure date (YYYY-MM-DD)
    """
    try:
        results = search_flights(origin, destination, depart_date)

        if "error" in results:
            return {"error": results["error"], "data": []}

        flights = results if isinstance(results, list) else results.get("data", [])

        if not flights:
            return {"data": [], "message": "No flights found for the given route/date."}

        # Filter by preferred airlines (if any)
        if ctx.deps.preferred_airlines:
            preferred_set = set(a.upper() for a in ctx.deps.preferred_airlines)

            def is_preferred(flight):
                airline_code = flight.get("airline", {}).get("iata", "").upper()
                return airline_code in preferred_set

            flights.sort(key=lambda f: (0 if is_preferred(f) else 1))

        # Format results
        formatted = []
        for flight in flights[:6]:
            try:
                airline = flight.get("airline", {}).get("name", "Unknown Airline")
                airline_code = flight.get("airline", {}).get("iata", "N/A")
                flight_number = flight.get("flight", {}).get("iata", "N/A")
                dep_iata = flight.get("departure", {}).get("iata", "N/A")
                dep_time = flight.get("departure", {}).get("scheduled", "N/A")
                arr_iata = flight.get("arrival", {}).get("iata", "N/A")
                arr_time = flight.get("arrival", {}).get("scheduled", "N/A")
                status = flight.get("flight_status", "N/A")

                formatted.append({
                    "airline": f"{airline} ({airline_code})",
                    "flight_number": flight_number,
                    "from": dep_iata,
                    "to": arr_iata,
                    "departure": dep_time,
                    "arrival": arr_time,
                    "status": status,
                    "raw_data": flight
                })
            except Exception as e:
                print(f"⚠️ Failed to format flight: {e}")
                continue

        return {
            "data": formatted,
            "total_results": len(formatted),
            "message": f"Found {len(formatted)} matching flights"
        }

    except Exception as e:
        return {"error": f"Flight search failed: {str(e)}", "data": []}
