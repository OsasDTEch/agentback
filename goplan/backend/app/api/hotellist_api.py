import requests


def get_hotel_list_hotellook(city, check_in, check_out, currency="usd", limit=10):
    """
    Search hotels in a city using HotelLook (TravelPayouts) public cache API.
    No authentication required.
    """
    url = "https://engine.hotellook.com/api/v2/cache.json"
    params = {
        "location": city,
        "checkIn": check_in,
        "checkOut": check_out,
        "currency": currency,
        "limit": limit
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if not data:
        return {"error": f"No hotels found in {city} for the given dates"}

    results = []
    for hotel in data:
        results.append({
            "name": hotel.get("hotelName"),
            "location": hotel.get("location", {}).get("name"),
            "country": hotel.get("location", {}).get("country"),
            "check_in": check_in,
            "check_out": check_out,
            "stars": hotel.get("stars"),
            "price_per_night": hotel.get("priceFrom"),
            "currency": currency,
            "geo": hotel.get("location", {}).get("geo", {}),
            "reason": "Found in budget range (cached data)"
        })

    return {"data": results}


if __name__ == "__main__":
    hotels = get_hotel_list_hotellook(
        city="Moscow",
        check_in="2025-08-12",
        check_out="2025-08-15",
        currency="usd",
        limit=5
    )
    print(hotels)
