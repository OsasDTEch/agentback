from pydantic_ai import Agent, RunContext
from typing import Any, List, Dict
from dataclasses import dataclass
import os
import httpx

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

provider = GoogleProvider(api_key=os.getenv('GOOGLE_API_KEY'))
model = GoogleModel('gemini-2.5-flash', provider=provider)

# Static city → IATA map (expand as needed)
city_to_iata = {
  "london": "LON", "new york": "NYC", "los angeles": "LAX", "paris": "PAR", "tokyo": "TYO",
    "berlin": "BER", "chicago": "CHI", "madrid": "MAD", "sydney": "SYD", "dubai": "DXB",
    "rome": "ROM", "toronto": "YTO", "moscow": "MOW", "amsterdam": "AMS", "beijing": "BJS",
    "delhi": "DEL", "bangkok": "BKK", "singapore": "SIN", "hong kong": "HKG", "seoul": "SEL",
    "boston": "BOS", "miami": "MIA", "atlanta": "ATL", "vienna": "VIE", "zurich": "ZRH",
    "lisbon": "LIS", "prague": "PRG", "warsaw": "WAW", "cairo": "CAI", "lagos": "LOS",
}

AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")  # Set this in env


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
    Search for flights using the AviationStack API.
    Args:
        origin: Origin city name
        destination: Destination city name
        depart_date: Departure date (not used in API directly)
        return_date: Return date (not used in API directly)
        budget_total: Budget limit (optional, not used here)
    """
    origin_code = city_to_iata.get(origin.lower())
    dest_code = city_to_iata.get(destination.lower())

    if not origin_code or not dest_code:
        return {
            "error": f"Invalid city name(s): origin='{origin}', destination='{destination}'",
            "data": []
        }

    try:
        url = f"http://api.aviationstack.com/v1/flights"
        params = {
            "access_key": AVIATIONSTACK_API_KEY,
            "dep_iata": origin_code,
            "arr_iata": dest_code,
            "limit": 6
        }
        response = httpx.get(url, params=params)
        res_json = response.json()

        flights = res_json.get("data", [])
        if not flights:
            return {"message": "No flights found.", "data": []}

        formatted_flights = []
        for f in flights:
            airline = f.get("airline", {}).get("name", "N/A")
            flight_num = f.get("flight", {}).get("number", "N/A")
            dep = f.get("departure", {})
            arr = f.get("arrival", {})

            formatted = {
                "airline": airline,
                "flight_number": flight_num,
                "departure_airport": dep.get("airport", "N/A"),
                "departure_time": dep.get("scheduled", "N/A"),
                "arrival_airport": arr.get("airport", "N/A"),
                "arrival_time": arr.get("scheduled", "N/A")
            }
            formatted_flights.append(formatted)

        return {
            "data": formatted_flights,
            "total_results": len(formatted_flights),
            "message": f"Found {len(formatted_flights)} flights from {origin.title()} to {destination.title()}"
        }

    except Exception as e:
        return {
            "error": f"Flight search failed: {str(e)}",
            "data": []
        }

