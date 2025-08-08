# weatherapi.py

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OPENWEATHER_APIKEY")

def get_weather_forecast(city: str, date: str) -> dict:
    """
    Fetch the weather forecast for a specific city and date.
    :param city: The city to check weather for.
    :param date: The date in 'YYYY-MM-DD' format.
    :return: Dictionary with weather details or error message.
    """
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"
        response = requests.get(url)

        if response.status_code != 200:
            return {"error": f"Failed to get weather for {city}. Status: {response.status_code}"}

        forecast_data = response.json()
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        matched_forecasts = []

        for entry in forecast_data.get("list", []):
            forecast_time = datetime.fromtimestamp(entry["dt"])
            if forecast_time.date() == target_date:
                matched_forecasts.append({
                    "time": forecast_time.strftime("%H:%M"),
                    "temperature": entry["main"]["temp"],
                    "weather": entry["weather"][0]["main"],
                    "description": entry["weather"][0]["description"]
                })

        if not matched_forecasts:
            return {"error": "No forecast available for the selected date."}

        return {"city": city, "date": date, "forecasts": matched_forecasts}

    except Exception as e:
        return {"error": str(e)}
