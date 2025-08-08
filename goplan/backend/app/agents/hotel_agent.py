
# ============= HOTELAGENT.PY (FIXED) =============
from pydantic_ai import Agent, RunContext
from typing import Any, List, Dict, Optional
from dataclasses import dataclass
import sys
import json
import os
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

# Import the fixed hotel search function
#  import get_hotel_list_hotellook
# For now, using the mock version for testing
from goplan.backend.app.api.hotellist_api import get_hotel_list_mock as get_hotel_list_hotellook

provider = GoogleProvider(api_key=os.getenv('GOOGLE_API_KEY'))

# Fixed model name - gemini-2.5-flash doesn't exist
model = GoogleModel('gemini-2.0-flash-exp', provider=provider)

@dataclass
class HotelDeps:
    hotel_amenities: Optional[List[str]] = None
    budget_level: Optional[str] = None

system_prompt = """
You are a hotel specialist in the Goplan AI Travel Planner.
Your role is to help users find the best accommodations for their trips using real API results.

Tools:
- Use the `search_hotels` tool to retrieve hotel options.
- The user's preferences (location, check-in/check-out dates, preferred amenities, star rating, budget level, and room type) are available in the GoplanState context.

Your workflow:
1. Read all available data in GoplanState:
   - destination city or area
   - check-in and check-out dates
   - budget_total (allocate up to 30% unless otherwise specified)
   - preferred amenities (e.g., Wi-Fi, breakfast included, pool, gym)
   - preferred star rating or quality level
   - preferred hotel chains if specified
2. Call the `search_hotels` tool to get realistic hotel options.
3. Select the best option(s) by balancing:
   - Best value within budget
   - High user ratings
   - Preferred amenities and location proximity
   - Preferred chain or style if given
4. If no hotel matches the budget, still return the best available option and log this in `errors`.

Reasoning:
- Always explain clearly why each hotel was chosen (e.g., "Best location near city center and free breakfast" or "Highest rating under budget with pool and Wi-Fi").
- Never ask for clarification before recommending — if data is missing, make the best plausible guess based on the destination and context.

Output format:
Return the updated GoplanState JSON including:
{
  "hotels": [
    {
      "name": "string",
      "address": "string",
      "city": "string",
      "check_in": "YYYY-MM-DD",
      "check_out": "YYYY-MM-DD",
      "price_per_night": "number",
      "currency": "string",
      "rating": "number",
      "amenities": ["string", ...],
      "booking_link": "string",
      "reason": "Why this hotel was selected"
    }
  ],
  "remaining_budget": "budget_total - (price_per_night * number_of_nights)",
  "errors": []
}
Do not overwrite unrelated fields in GoplanState.
"""

hotel_agent = Agent(
    model,
    system_prompt=system_prompt,
    deps_type=HotelDeps,
    retries=2
)

@hotel_agent.tool
async def search_hotels(
    ctx: RunContext[HotelDeps],
    city: str,
    check_in: str,
    check_out: str,
    max_price: Optional[float] = None
) -> List[dict]:
    """
    Search and filter hotels based on user preferences using HotelLook API.
    """
    try:
        hotel_data = get_hotel_list_hotellook(city, check_in, check_out)
    except Exception as e:
        return [{"error": f"Hotel search failed: {str(e)}"}]

    if isinstance(hotel_data, dict) and "error" in hotel_data:
        return [hotel_data]

    if isinstance(hotel_data, dict):
        hotel_options = hotel_data.get("data", [])
    else:
        hotel_options = hotel_data if isinstance(hotel_data, list) else []

    if not isinstance(hotel_options, list):
        return [{"error": "Invalid hotel data format"}]

    # Filter by max price if specified
    if max_price is not None:
        try:
            filtered_hotels = [
                h for h in hotel_options
                if float(h.get("price_per_night", 0)) <= max_price
            ]
        except (ValueError, TypeError):
            filtered_hotels = hotel_options
    else:
        filtered_hotels = hotel_options

    # Get preferences from context
    preferred_amenities = ctx.deps.hotel_amenities or []
    budget_level = ctx.deps.budget_level

    # Process hotels and add missing fields
    for hotel in filtered_hotels:
        # Ensure required fields exist
        hotel.setdefault("matching_amenities", [])
        hotel.setdefault("preference_score", 0)
        hotel.setdefault("rating", hotel.get("stars", 0))
        hotel.setdefault("booking_link", "")
        hotel.setdefault("amenities", ["Wi-Fi", "Reception"])

        # Create address from location and country
        hotel["address"] = ", ".join(filter(None, [
            hotel.get("location", ""),
            hotel.get("country", "")
        ]))

        # Ensure city field exists
        hotel["city"] = city

    # Sort by budget level preference
    if budget_level:
        if budget_level.lower() == "budget":
            filtered_hotels.sort(
                key=lambda x: float(x.get("price_per_night", 0))
            )
        elif budget_level.lower() == "luxury":
            filtered_hotels.sort(
                key=lambda x: float(x.get("price_per_night", 0)),
                reverse=True
            )
        else:  # mid-range
            filtered_hotels.sort(
                key=lambda x: (
                    abs(float(x.get("price_per_night", 0)) - 150),  # Target mid-range price
                    -float(x.get("stars", 0))  # Prefer higher stars
                )
            )

    return filtered_hotels[:10]  # Return top 10 results

