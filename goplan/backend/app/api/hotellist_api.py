# ============= HOTELSEARCH.PY (FIXED) =============
import requests
from datetime import datetime
import time

def get_hotel_list_hotellook(city, check_in, check_out, currency="usd", limit=10):
    """
    Search hotels in a city using HotelLook (TravelPayouts) public cache API.
    No authentication required.
    """
    
    # Validate date format
    try:
        datetime.strptime(check_in, '%Y-%m-%d')
        datetime.strptime(check_out, '%Y-%m-%d')
    except ValueError:
        return {"error": "Dates must be in YYYY-MM-DD format"}
    
    # The correct HotelLook API endpoint and parameters
    url = "https://engine.hotellook.com/api/v2/lookup.json"
    params = {
        "query": city,
        "lang": "en",
        "lookFor": "both",  # hotels and locations
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data or "results" not in data:
            return {"error": f"No hotels found in {city}"}
        
        results = []
        hotels_data = data.get("results", {}).get("hotels", [])
        
        if not hotels_data:
            return {"error": f"No hotels found in {city} for the given dates"}
        
        for hotel in hotels_data[:limit]:
            # Extract hotel information from the API response
            hotel_info = {
                "name": hotel.get("label", "Unknown Hotel"),
                "location": hotel.get("location_name", city),
                "country": hotel.get("country_name", ""),
                "check_in": check_in,
                "check_out": check_out,
                "stars": hotel.get("stars", 0),
                "price_per_night": hotel.get("min_rate", 100),  # Default price if not available
                "currency": currency,
                "hotel_id": hotel.get("id"),
                "reason": "Available hotel option"
            }
            results.append(hotel_info)
        
        return {"data": results}
        
    except requests.exceptions.Timeout:
        return {"error": "Request timeout - API took too long to respond"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

# Alternative function using a mock data approach (since HotelLook API has limitations)
def get_hotel_list_mock(city, check_in, check_out, currency="usd", limit=10):
    """
    Mock hotel search function for testing purposes.
    Returns sample hotel data with realistic information.
    """
    
    # Validate date format
    try:
        datetime.strptime(check_in, '%Y-%m-%d')
        datetime.strptime(check_out, '%Y-%m-%d')
    except ValueError:
        return {"error": "Dates must be in YYYY-MM-DD format"}
    
    # Mock hotel data based on popular cities
    mock_hotels = {
        "moscow": [
            {"name": "Hotel Metropol Moscow", "stars": 5, "price": 250},
            {"name": "Radisson Collection Hotel", "stars": 5, "price": 200},
            {"name": "Holiday Inn Moscow", "stars": 4, "price": 150},
            {"name": "Ibis Moscow Centre", "stars": 3, "price": 100},
            {"name": "Hostel Rus Red Square", "stars": 2, "price": 50}
        ],
        "london": [
            {"name": "The Ritz London", "stars": 5, "price": 500},
            {"name": "Hilton London Park Lane", "stars": 5, "price": 350},
            {"name": "Premier Inn London", "stars": 4, "price": 120},
            {"name": "Travelodge London", "stars": 3, "price": 80},
            {"name": "YHA London Central", "stars": 2, "price": 40}
        ],
        "paris": [
            {"name": "Le Bristol Paris", "stars": 5, "price": 800},
            {"name": "Hotel Plaza Athénée", "stars": 5, "price": 600},
            {"name": "Novotel Paris Centre", "stars": 4, "price": 180},
            {"name": "Ibis Paris Opera", "stars": 3, "price": 120},
            {"name": "Hotel des Jeunes", "stars": 2, "price": 60}
        ]
    }
    
    city_lower = city.lower()
    if city_lower not in mock_hotels:
        # Default hotels for unknown cities
        city_hotels = [
            {"name": f"Grand Hotel {city}", "stars": 5, "price": 300},
            {"name": f"City Inn {city}", "stars": 4, "price": 150},
            {"name": f"Budget Lodge {city}", "stars": 3, "price": 80},
            {"name": f"Backpacker Hostel {city}", "stars": 2, "price": 40}
        ]
    else:
        city_hotels = mock_hotels[city_lower]
    
    results = []
    for i, hotel in enumerate(city_hotels[:limit]):
        hotel_info = {
            "name": hotel["name"],
            "location": city,
            "country": "Various",
            "check_in": check_in,
            "check_out": check_out,
            "stars": hotel["stars"],
            "price_per_night": hotel["price"],
            "currency": currency,
            "hotel_id": f"hotel_{i+1}",
            "reason": f"{hotel['stars']}-star hotel with good amenities"
        }
        results.append(hotel_info)
    
    return {"data": results}

# Test function
if __name__ == "__main__":  # Fixed the syntax error
    print("Testing HotelLook API...")
    hotels = get_hotel_list_hotellook(
        city="Moscow",
        check_in="2025-08-12",
        check_out="2025-08-15",
        currency="usd",
        limit=5
    )
    print("HotelLook Results:")
    print(hotels)
    
    print("\nTesting Mock API...")
    hotels_mock = get_hotel_list_mock(
        city="Moscow",
        check_in="2025-08-12",
        check_out="2025-08-15",
        currency="usd",
        limit=5
    )
    print("Mock Results:")
    print(hotels_mock)
