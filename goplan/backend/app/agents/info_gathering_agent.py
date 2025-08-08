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

# Initialize the calendar parser once
cal = parsedatetime.Calendar()

def parse_natural_date_to_iso(date_input: str) -> Optional[str]:
    """
    Convert natural language date to ISO 8601 (YYYY-MM-DD) format.
    Ensures the parsed date is in the future relative to today.
    """
    if not date_input:
        return None

    try:
        now = datetime.now()
        time_struct, parse_status = cal.parse(date_input, now)

        if parse_status == 0:
            return None  # parsing failed

        parsed_date = datetime(*time_struct[:6])

        # If parsed date is in the past, adjust to next year
        if parsed_date.date() < now.date():
            # Instead of re-parsing, just add a year to the parsed date
            parsed_date = parsed_date.replace(year=parsed_date.year + 1)

        return parsed_date.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Date parsing error: {e}")  # Add this for debugging
        return None

class TravelDetails(BaseModel):
    """Structured information extracted from the user about their trip."""

    response: str = Field(
        description="A message for the user confirming what you understood or asking for missing details.")

    destination: Optional[str] = Field(default=None, description="The city or country the user is traveling to.")
    origin: Optional[str] = Field(default=None, description="The city or country the user is flying from.")

    date_leaving: Optional[str] = Field(default=None, description="Date of departure (format: MM-DD)")
    date_returning: Optional[str] = Field(default=None, description="Date of return (format: MM-DD)")

    max_hotel_price: Optional[int] = Field(default=None, description="Maximum hotel price per night in USD.")

    all_details_given: bool = Field(description="True if all fields are filled. Otherwise False.")

    @field_validator('date_leaving', 'date_returning', mode='before')
    @classmethod
    def parse_dates(cls, v):
        """Automatically parse natural language dates to MM-DD format"""
        if v is None:
            return v
        if isinstance(v, str):
            # Try to parse as natural language date
            parsed = parse_natural_date_to_iso(v)
            return parsed if parsed else v
        return v


# Enhanced system prompt with date parsing instructions
system_prompt = """
You are a helpful travel planning assistant with advanced date understanding capabilities.

Your job is to collect the following details from the user for planning their trip:
- Destination (where they are going)
- Origin (where they are flying from)  
- Departure date (you can understand natural language like "next friday", "in 3 days", "march 15th")
- Return date (you can understand natural language dates)
- Maximum hotel price per night (in USD)

IMPORTANT DATE HANDLING:
- Users can say dates in natural language like "next tomorrow", "in 5 days", "march 15th", "next friday"
- You should understand and accept these natural formats
- The system will automatically convert them to YYYY-MM-DD format
- Always acknowledge the dates you understood in your response

Examples of date inputs you can handle:
- "next friday" 
- "in two weeks"
- "march 15th"
- "tomorrow"
- "next month"
- "december 25"

Always respond clearly:
- If any details are missing, tell the user exactly what is missing and ask for it
- When you understand a date, confirm it back to them (e.g., "I understand you're leaving next Friday")
- If all details are present, confirm the complete trip plan in a friendly, helpful tone
- If a date seems unclear, ask for clarification

Respond concisely and clearly. Your output should include both the structured data and a user-facing message in the `response` field.
"""

info_gathering_agent = Agent(
    model=model,
    output_type=TravelDetails,
    system_prompt=system_prompt,
    retries=2
)


# Example usage function
async def process_travel_request(user_input: str):
    """
    Process a user's travel request with natural language date parsing
    """
    try:
        result = await info_gathering_agent.run(user_input)
        return result.data
    except Exception as e:
        return f"Error processing request: {e}"


# Example of how to test this
if __name__ == "__main__":
    import asyncio


    async def test_examples():
        examples = [
            "I want to go to Paris from New York, leaving next friday and coming back in two weeks",
            "Plan a trip to Tokyo, departing march 15th, budget is $200 per night",
            "I'm going to London next tomorrow, returning in 5 days, from Chicago"
        ]

        for example in examples:
            print(f"\nUser: {example}")
            result = await process_travel_request(example)
            print(f"Agent: {result}")

    # Uncomment to test:
    asyncio.run(test_examples())