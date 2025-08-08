# ============= FLIGHTSEARCHAPI.PY (FIXED) =============
import requests
import os  # Added missing import
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
    
    # Check if API key is available
    api_key = os.getenv('AVIATIONSTACK_API_KEY')  # Fixed environment variable name
    if not api_key:
        return {"error": "AVIATIONSTACK_API_KEY environment variable not set"}

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

    try:
        # Use HTTPS instead of HTTP
        url = "https://api.aviationstack.com/v1/flights"
        params = {
            "access_key": api_key,  # Fixed variable name
            "dep_iata": origin_code,
            "arr_iata": destination_code,
            "limit": 6
        }

        response = requests.get(url, params=params, timeout=30)  # Added timeout

        if response.status_code != 200:
            return {"error": f"API error: {response.status_code} - {response.text}"}

        result = response.json()
        
        # Check for API errors in response
        if "error" in result:
            return {"error": f"API Error: {result['error']}"}
            
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

        return {
            "data": flights,
            "search_params": {
                "origin": f"{origin_name} ({origin_code})",
                "destination": f"{destination_name} ({destination_code})",
                "depart_date": depart_date,
                "adults": adults
            }
        }

    except requests.exceptions.Timeout:
        return {"error": "Request timeout - API took too long to respond"}
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

