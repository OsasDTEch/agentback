from goplan.backend.app.api.accs import get_access_token
import requests


def get_city_code(city_name):
    """Get city code (IATA) for hotels."""
    token = get_access_token()
    url = "https://test.api.amadeus.com/v1/reference-data/locations/cities"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"keyword": city_name}
    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    data = res.json().get("data", [])
    return data[0]["iataCode"] if data else None


def get_hotel_list(city_code):
    """Get hotels in a given city."""
    token = get_access_token()
    url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"cityCode": city_code}
    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    return res.json().get("data", [])


def search_hotels_availability(hotel_ids, check_in, check_out, max_price=None):
    """Get availability, price, and amenities for given hotels."""
    token = get_access_token()
    url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
    headers = {"Authorization": f"Bearer {token}"}

    valid_offers = []

    # Process in batches of 5 to avoid bad IDs breaking everything
    for i in range(0, len(hotel_ids), 5):
        batch_ids = hotel_ids[i:i + 5]
        params = {
            "hotelIds": ",".join(batch_ids),
            "checkInDate": check_in,
            "checkOutDate": check_out,
            "adults": 1
        }
        if max_price:
            params["priceRange"] = f"0-{max_price}"

        res = requests.get(url, headers=headers, params=params)

        if res.status_code == 400:
            print(f"⚠️ Skipping invalid hotel batch: {batch_ids}")
            continue

        res.raise_for_status()
        valid_offers.extend(res.json().get("data", []))

    return valid_offers


def search_hotels_combined(city, check_in, check_out, max_price=None):
    """
    Full pipeline:
    1. Get hotels list by city (Hotel List API)
    2. Search offers for those hotels (Hotel Search API)
    """
    city_code = get_city_code(city)
    if not city_code:
        return {"error": f"City code not found for {city}"}

    hotel_list = get_hotel_list(city_code)
    if not hotel_list:
        return {"error": "No hotels found"}

    # Limit to first 20 hotels to avoid API limits
    hotel_ids = [hotel["hotelId"] for hotel in hotel_list[:20]]

    availability = search_hotels_availability(hotel_ids, check_in, check_out, max_price)

    merged_results = []
    hotel_info_map = {h["hotelId"]: h for h in hotel_list}

    for offer in availability:
        hotel_id = offer["hotel"]["hotelId"]
        basic_info = hotel_info_map.get(hotel_id, {})

        if not offer.get("offers"):
            continue

        merged_results.append({
            "name": basic_info.get("name"),
            "address": basic_info.get("address", {}).get("lines", []),
            "city": basic_info.get("address", {}).get("cityName"),
            "check_in": check_in,
            "check_out": check_out,
            "price_per_night": offer["offers"][0]["price"]["total"],
            "currency": offer["offers"][0]["price"]["currency"],
            "rating": basic_info.get("rating"),
            "amenities": offer["hotel"].get("amenities", []),
            "booking_link": offer["offers"][0]["self"],
            "reason": "Matched budget and location preferences"
        })

    return {"data": merged_results}


if __name__ == "__main__":
    print(
        search_hotels_combined(
            "London",
            "2025-08-12",
            "2025-08-18",
            max_price=None
        )
    )
