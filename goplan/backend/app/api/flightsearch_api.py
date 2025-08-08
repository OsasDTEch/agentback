import requests
from datetime import datetime, timezone


# ✅ Static mapping: 30 popular cities
CITY_TO_IATA = {
    "new york": "JFK",
    "london": "LON",
    "paris": "CDG",
    "dubai": "DXB",
    "tokyo": "HND",
    "los angeles": "LAX",
    "toronto": "YYZ",
    "sydney": "SYD",
    "rome": "FCO",
    "amsterdam": "AMS",
    "frankfurt": "FRA",
    "singapore": "SIN",
    "istanbul": "IST",
    "barcelona": "BCN",
    "bangkok": "BKK",
    "seoul": "ICN",
    "madrid": "MAD",
    "chicago": "ORD",
    "san francisco": "SFO",
    "lisbon": "LIS",
    "nairobi": "NBO",
    "cape town": "CPT",
    "lagos": "LOS",
    "johannesburg": "JNB",
    "mexico city": "MEX",
    "buenos aires": "EZE",
    "cairo": "CAI",
    "athens": "ATH",
    "vienna": "VIE",
    "helsinki": "HEL"
}


def get_city_code(keyword):
    """Return IATA code from static city lookup"""
    keyword_lower = keyword.lower()
    if keyword_lower in CITY_TO_IATA:
        return CITY_TO_IATA[keyword_lower]
    raise ValueError(f"City '{keyword}' not found in supported list")


def validate_date(date_string):
    """Ensure date is in YYYY-MM-DD and in the future"""
    try:
        flight_date = datetime.strptime(date_string, '%Y-%m-%d').date()
        today = datetime.now(timezone.utc).date()
        if flight_date <= today:
            raise ValueError(f"Date {date_string} must be in the future")
        return True
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_string}. Use YYYY-MM-DD. {str(e)}")


def search_flights(origin_name, destination_name, depart_date, return_date=None,
                   adults=1, max_price=None):
    """
    Search flights using Aviationstack API
    - Return date and max_price are ignored (Aviationstack doesn't support them)
    """

    try:
        # Validate input dates
        validate_date(depart_date)
        if return_date:
            validate_date(return_date)

        # Get static codes
        origin_code = get_city_code(origin_name)
        destination_code = get_city_code(destination_name)

    except ValueError as e:
        return {"error": str(e)}

    # Aviationstack doesn't support real-time search for future flights,
    # only live flights or historical. So we simulate the "search" by querying live flights
    # between the IATA codes (best we can do with free version)

    try:
        url = "http://api.aviationstack.com/v1/flights"
        params = {
            "access_key": os.getenv('AVIATION_APIKEY),  # <-- Replace this
            "dep_iata": origin_code,
            "arr_iata": destination_code,
            "limit": 6
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            return {"error": f"API error: {response.status_code} - {response.text}"}

        result = response.json()
        flights = result.get("data", [])

        if not flights:
            return {
                "data": [],
                "message": "No flights found for selected route",
                "search_params": {
                    "origin": f"{origin_name} ({origin_code})",
                    "destination": f"{destination_name} ({destination_code})",
                    "depart_date": depart_date,
                    "adults": adults
                }
            }

        # Optionally enrich static airline names, etc.
        return {
            "data": flights,
            "search_params": {
                "origin": f"{origin_name} ({origin_code})",
                "destination": f"{destination_name} ({destination_code})",
                "depart_date": depart_date,
                "adults": adults
            }
        }

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# ✅ Example usage
if __name__ == "__main__":
    flights = search_flights(
        "London",
        "New York",
        "2025-09-15"
    )

    if "error" in flights:
        print(f"❌ Error: {flights['error']}")
    else:
        print(f"✅ Found {len(flights.get('data', []))} flights")
        for i, flight in enumerate(flights["data"][:3]):
            airline = flight.get("airline", {}).get("name", "Unknown Airline")
            flight_number = flight.get("flight", {}).get("iata", "N/A")
            dep = flight.get("departure", {}).get("airport", "Unknown")
            arr = flight.get("arrival", {}).get("airport", "Unknown")
            print(f"✈️ {airline} {flight_number} from {dep} → {arr}")
