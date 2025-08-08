#using aviastack api for flight: check this api code: to work with it?
from goplan.backend.app.api.accs import get_access_token
import requests
from datetime import datetime, date, timezone


def get_city_or_airport_code(keyword):
    """
    Search IATA code for flights (CITY or AIRPORT).
    Automatically picks the best match from Amadeus data.
    Returns tuple: (iataCode, countryCode)
    """
    token = get_access_token()
    url = "https://test.api.amadeus.com/v1/reference-data/locations"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"keyword": keyword, "subType": "AIRPORT,CITY"}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json().get("data", [])

    if not data:
        raise ValueError(f"No location found for '{keyword}'")

    # Prefer exact match ignoring case
    for item in data:
        if item["name"].lower() == keyword.lower():
            return item["iataCode"], item.get("address", {}).get("countryCode")

    # Fallback: return first result
    first = data[0]
    return first["iataCode"], first.get("address", {}).get("countryCode")


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


def search_flights(origin_name, destination_name, depart_date, return_date,
                   adults=1, max_price=None):
    """
    Search flights between two cities/airports using Amadeus API.
    - max_price is optional
    - Automatically detects country codes
    - Validates dates are in the future
    """
    try:
        # Validate dates first
        validate_date(depart_date)
        validate_date(return_date)

        # Validate that return date is after departure date
        dep_date = datetime.strptime(depart_date, '%Y-%m-%d').date()
        ret_date = datetime.strptime(return_date, '%Y-%m-%d').date()

        if ret_date <= dep_date:
            raise ValueError("Return date must be after departure date")

        # Get IATA codes
        origin_code, origin_country = get_city_or_airport_code(origin_name)
        destination_code, destination_country = get_city_or_airport_code(destination_name)

    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Location lookup failed: {str(e)}"}

    try:
        token = get_access_token()
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        headers = {"Authorization": f"Bearer {token}"}

        params = {
            "originLocationCode": origin_code,
            "destinationLocationCode": destination_code,
            "departureDate": depart_date,
            "returnDate": return_date,
            "adults": adults,
            "currencyCode": "USD",
            "max": 6
        }

        # Add max_price only if provided and valid
        if max_price is not None and max_price > 0:
            params["maxPrice"] = int(max_price)

        response = requests.get(url, headers=headers, params=params)

        # Handle different HTTP errors
        if response.status_code == 400:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get('errors', [{}])[0].get('detail', 'Bad request - check your search parameters')
            return {"error": f"Search parameters invalid: {error_msg}"}
        elif response.status_code == 401:
            return {"error": "Authentication failed - check API credentials"}
        elif response.status_code == 429:
            return {"error": "Rate limit exceeded - please try again later"}

        response.raise_for_status()
        result = response.json()

        # Check if API returned any data
        if not result.get("data"):
            return {
                "data": [],
                "message": "No flights found for the specified criteria",
                "search_params": {
                    "origin": f"{origin_name} ({origin_code})",
                    "destination": f"{destination_name} ({destination_code})",
                    "depart_date": depart_date,
                    "return_date": return_date,
                    "adults": adults,
                    "max_price": max_price
                }
            }

        return result

    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# Example usage
if __name__ == "__main__":
    flights = search_flights(
        "New York",
        "Paris",
        "2025-09-15",
        "2025-09-22",
        adults=1,
        max_price=1500  # optional
    )

    if "error" in flights:
        print(f"Error: {flights['error']}")
    else:
        print(f"Found {len(flights.get('data', []))} flights")
        for i, flight in enumerate(flights.get('data', [])[:3]):  # Show first 3
            price = flight.get('price', {}).get('total', 'N/A')
            currency = flight.get('price', {}).get('currency', 'USD')
            print(f"Flight {i + 1}: {price} {currency}")
