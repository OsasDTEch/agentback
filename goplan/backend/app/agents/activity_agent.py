from pydantic_ai import Agent, RunContext
from typing import Optional
from dataclasses import dataclass
# Import with a different name to avoid naming conflict
from goplan.backend.app.api.weatherapi import get_weather_forecast as fetch_weather_data

import os
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

# Set up the model
provider = GoogleProvider(api_key=os.getenv("GOOGLE_API_KEY"))
model = GoogleModel("gemini-2.5-flash", provider=provider)


# Define dependencies (if you later want to add interests or duration)
@dataclass
class ActivityDeps:
    interests: Optional[list[str]] = None
    trip_length: Optional[int] = None  # in days
    budget_level: Optional[str] = None


# Stronger, cleaner system prompt
system_prompt = """
You are an intelligent travel planning assistant helping users plan meaningful activities for their trips.

Your main role is to:
- Recommend personalized activities based on city, date, weather, and user preferences.
- Use the `get_weather_forecast` tool to fetch forecast information before deciding.
- Adjust recommendations based on weather: sunny = outdoor; rainy = indoor.

Format your response like:
- Activity: [title]
  Reason: [why it fits, especially in this weather]

Never ask for clarification — just assume sensible defaults (e.g. 3-day trip, average interests in food, culture, nature, and exploration).
"""

activity_agent = Agent(
    model=model,
    system_prompt=system_prompt,
    deps_type=ActivityDeps,
    retries=2,
)


@activity_agent.tool_plain
async def get_weather_forecast(city: str, date: str) -> str:
    """
    Fetch weather forecast for a specific city and date using OpenWeather API.
    """
    # Use the imported function with the different name
    data = fetch_weather_data(city, date)

    if "error" in data:
        return f"Weather data for {city} on {date} is unavailable. ({data['error']})"

    forecasts = data.get("forecasts", [])
    if not forecasts:
        return f"No forecast data available for {city} on {date}."

    summaries = []
    for forecast in forecasts:
        summaries.append(
            f"{forecast['time']}: {forecast['weather']} ({forecast['description']}, {forecast['temperature']}°C)"
        )

    forecast_text = "\n".join(summaries)
    avg_temp = round(sum(f['temperature'] for f in forecasts) / len(forecasts), 1)

    return (
        f"Weather forecast for {city.title()} on {date}:\n{forecast_text}\n"
        f"Average Temp: ~{avg_temp}°C"
    )