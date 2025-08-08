import os
import requests
from dotenv import load_dotenv

load_dotenv()
AMADEUS_API_KEY = os.getenv("AMADEUS_APIKEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_APISECRET")


def get_access_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET
    }
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]
