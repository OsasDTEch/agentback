import requests
from dotenv import load_dotenv
from datetime import datetime, timezone
load_dotenv()
AVIATIONSTACK_API_KEY = os.getenv('AVIATION_APIKEY')
BASE_URL = "http://api.aviationstack.com/v1"


def validate_date(date_string):
    """Validate that the date is in the future and in correct format"""
    try:
        flight_date = datetime.strptime(date_string, '%Y-%m-%d').date()
        today = datetime.now(timezone.utc).date()

        print(f"🕐 Validating: {flight_date} vs today: {today}")

        if flight_date <= today:
            raise ValueError(f"Date {date_string} must be in the future")

        return True
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_string}'. Use YYYY-MM-DD format. {str(e)}")


def search_flights(origin_iata, destination_iata, depart_date):
    """
    Search flights using Aviationstack API.
    Note: This only shows live/historical flights, NOT booking/prices.
    """
    try:
        validate_date(depart_date)

        params = {
            "access_key": AVIATIONSTACK_API_KEY,
            "dep_iata": origin_iata,
            "arr_iata": destination_iata,
            "flight_date": depart_date,
        }

        response = requests.get(f"{BASE_URL}/flights", params=params)

        if response.status_code != 200:
            return {"error": f"Aviationstack API error: {response.text}"}

        data = response.json().get("data", [])

        if not data:
            return {
                "data": [],
                "message": "No flights found for the specified criteria",
                "search_params": {
                    "origin": origin_iata,
                    "destination": destination_iata,
                    "depart_date": depart_date
                }
            }

        return data

    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# 🔎 Example usage
if __name__ == "__main__":
    flights = search_flights(
        origin_iata="LHR",     # London Heathrow
        destination_iata="DEL",  # Delhi Indira Gandhi
        depart_date="2025-09-09"
    )

    if "error" in flights:
        print(f"❌ Error: {flights['error']}")
    else:
        print(f"✅ Found {len(flights)} flights")
        for i, flight in enumerate(flights[:3]):  # Show first 3 flights
            flight_number = flight.get("flight", {}).get("iata", "N/A")
            airline = flight.get("airline", {}).get("name", "Unknown Airline")
            status = flight.get("flight_status", "unknown")
            dep_time = flight.get("departure", {}).get("scheduled", "N/A")
            print(f"✈️ Flight {flight_number} ({airline}) - Departs: {dep_time} - Status: {status}")
