from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from typing import Optional
from pydantic import Field, BaseModel, field_validator
from dataclasses import dataclass
import os
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
import parsedatetime
from datetime import datetime
load_dotenv()
# Set up the model
provider = GoogleProvider(api_key=os.getenv("GOOGLE_API_KEY"))
model = GoogleModel("gemini-2.5-flash", provider=provider)

system_prompt = """
You are a travel agent expert helping people plan their perfect trip.

You will be given flight, hotel, and activity recommendations, and it's your job to take all
of that information and summarize it in a neat final package to give to the user as your
final recommendation for their trip.
"""

final_planner_agent = Agent(model, system_prompt=system_prompt)