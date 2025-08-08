import uuid
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from typing import Annotated, Dict, List, Any, Optional
from typing_extensions import TypedDict
from langgraph.types import interrupt
from pydantic import ValidationError
from dataclasses import dataclass
import asyncio
import sys
import os

# Import the message classes from Pydantic AI
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter
)

# Updated imports with error handling for missing agents
try:
    from goplan.backend.app.agents.info_gathering_agent import info_gathering_agent, TravelDetails
except ImportError:
    print("⚠️ Warning: info_gathering_agent not found")
    info_gathering_agent = None
    TravelDetails = dict

try:
    from goplan.backend.app.agents.flight_agent import flight_agent, FlightDeps
except ImportError:
    print("⚠️ Warning: flight_agent not found")
    flight_agent = None
    FlightDeps = dict

try:
    from goplan.backend.app.agents.hotel_agent import hotel_agent, HotelDeps
except ImportError:
    print("⚠️ Warning: hotel_agent not found")
    hotel_agent = None
    HotelDeps = dict

try:
    from goplan.backend.app.agents.activity_agent import activity_agent
except ImportError:
    print("⚠️ Warning: activity_agent not found")
    activity_agent = None

try:
    from goplan.backend.app.agents.final_planner_agent import final_planner_agent
except ImportError:
    print("⚠️ Warning: final_planner_agent not found")
    final_planner_agent = None


# Define the state for our graph
class TravelState(TypedDict):
    # Chat messages and travel details
    thread_id: str
    user_input: str
    messages: Annotated[List[bytes], lambda x, y: x + y]
    travel_details: Dict[str, Any]

    # User preferences
    preferred_airlines: List[str]
    hotel_amenities: List[str]
    budget_level: str

    # Results from each agent
    flight_results: str
    hotel_results: str
    activity_results: str

    # Final summary
    final_plan: str
    
    # Error tracking
    errors: List[str]


# Node functions for the graph
async def gather_info(state: TravelState, *, config) -> Dict[str, Any]:
    """Gather necessary travel information from the user."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)
    
    if not info_gathering_agent:
        return {
            "travel_details": {"error": "Info gathering agent not available"},
            "errors": ["Info gathering agent not found"],
            "messages": []
        }
    
    user_input = state["user_input"]
    writer("🔍 Gathering travel information...\n")

    try:
        # Get the message history into the format for Pydantic AI
        message_history: list[ModelMessage] = []
        for message_row in state.get('messages', []):
            try:
                message_history.extend(ModelMessagesTypeAdapter.validate_json(message_row))
            except Exception as e:
                print(f"Warning: Could not parse message history: {e}")

        # Call the info gathering agent
        async with info_gathering_agent.run_stream(user_input, message_history=message_history) as result:
            curr_response = ""
            travel_details = None

            async for message, last in result.stream_structured(debounce_by=0.01):
                try:
                    # Fixed method name - use get_structured_output instead
                    travel_details = await result.get_structured_output(
                        message,
                        allow_partial=not last
                    )
                    if last and not travel_details.response:
                        raise Exception("Incorrect travel details returned by the agent.")
                except ValidationError as e:
                    continue
                except AttributeError:
                    # Fallback if method name is different
                    try:
                        travel_details = message
                    except:
                        continue

                if travel_details and hasattr(travel_details, 'response') and travel_details.response:
                    new_content = travel_details.response[len(curr_response):]
                    if new_content:
                        writer(new_content)
                    curr_response = travel_details.response

        # Get the final output
        data = await result.get_output()
        writer("✅ Travel information gathered successfully!\n")
        
        return {
            "travel_details": data.model_dump() if hasattr(data, 'model_dump') else data,
            "messages": [result.new_messages_json()],
            "errors": []
        }
        
    except Exception as e:
        writer(f"❌ Error gathering travel info: {str(e)}\n")
        return {
            "travel_details": {"error": str(e)},
            "errors": [f"Info gathering failed: {str(e)}"],
            "messages": []
        }


async def get_flight_recommendations(state: TravelState, *, config) -> Dict[str, Any]:
    """Get flight recommendations based on travel details."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("✈️ Getting flight recommendations...\n")

    if not flight_agent:
        writer("❌ Flight agent not available\n")
        return {
            "flight_results": "Flight search service temporarily unavailable",
            "errors": ["Flight agent not found"]
        }

    travel_details = state["travel_details"]
    preferred_airlines = state.get('preferred_airlines', [])

    # Check if travel details contain errors
    if "error" in travel_details:
        return {
            "flight_results": "Cannot search flights due to incomplete travel details",
            "errors": ["Travel details incomplete"]
        }

    try:
        # Create flight dependencies
        if FlightDeps != dict:
            flight_dependencies = FlightDeps(preferred_airlines=preferred_airlines)
        else:
            flight_dependencies = {"preferred_airlines": preferred_airlines}

        # Prepare the prompt for the flight agent
        origin = travel_details.get('origin', 'Unknown')
        destination = travel_details.get('destination', 'Unknown')
        date_leaving = travel_details.get('date_leaving', 'Unknown')
        date_returning = travel_details.get('date_returning', 'Unknown')
        
        prompt = f"I need flight recommendations from {origin} to {destination} on {date_leaving}. Return flight on {date_returning}."

        # Call the flight agent
        if FlightDeps != dict:
            result = await flight_agent.run(prompt, deps=flight_dependencies)
        else:
            result = await flight_agent.run(prompt)
            
        writer("✅ Flight recommendations retrieved successfully!\n")
        return {
            "flight_results": str(result.data) if hasattr(result, 'data') else str(result),
            "errors": []
        }
        
    except Exception as e:
        writer(f"❌ Error getting flight recommendations: {str(e)}\n")
        return {
            "flight_results": f"Flight search temporarily unavailable: {str(e)}",
            "errors": [f"Flight search failed: {str(e)}"]
        }


async def get_hotel_recommendations(state: TravelState, *, config) -> Dict[str, Any]:
    """Get hotel recommendations based on travel details."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("🏨 Getting hotel recommendations...\n")

    if not hotel_agent:
        writer("❌ Hotel agent not available\n")
        return {
            "hotel_results": "Hotel search service temporarily unavailable",
            "errors": ["Hotel agent not found"]
        }

    travel_details = state["travel_details"]
    hotel_amenities = state.get('hotel_amenities', [])
    budget_level = state.get('budget_level', 'medium')

    # Check if travel details contain errors
    if "error" in travel_details:
        return {
            "hotel_results": "Cannot search hotels due to incomplete travel details",
            "errors": ["Travel details incomplete"]
        }

    try:
        # Create hotel dependencies
        if HotelDeps != dict:
            hotel_dependencies = HotelDeps(
                hotel_amenities=hotel_amenities,
                budget_level=budget_level
            )
        else:
            hotel_dependencies = {
                "hotel_amenities": hotel_amenities,
                "budget_level": budget_level
            }

        # Prepare the prompt for the hotel agent
        destination = travel_details.get('destination', 'Unknown')
        date_leaving = travel_details.get('date_leaving', 'Unknown')
        date_returning = travel_details.get('date_returning', 'Unknown')
        max_hotel_price = travel_details.get('max_hotel_price', '200')
        
        prompt = f"I need hotel recommendations in {destination} from {date_leaving} to {date_returning} with a maximum price of ${max_hotel_price} per night."

        # Call the hotel agent
        if HotelDeps != dict:
            result = await hotel_agent.run(prompt, deps=hotel_dependencies)
        else:
            result = await hotel_agent.run(prompt)
            
        writer("✅ Hotel recommendations retrieved successfully!\n")
        return {
            "hotel_results": str(result.data) if hasattr(result, 'data') else str(result),
            "errors": []
        }
        
    except Exception as e:
        writer(f"❌ Error getting hotel recommendations: {str(e)}\n")
        return {
            "hotel_results": f"Hotel search temporarily unavailable: {str(e)}",
            "errors": [f"Hotel search failed: {str(e)}"]
        }


async def get_activity_recommendations(state: TravelState, *, config) -> Dict[str, Any]:
    """Get activity recommendations based on travel details."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("🎯 Getting activity recommendations...\n")

    if not activity_agent:
        writer("❌ Activity agent not available\n")
        return {
            "activity_results": "Activity search service temporarily unavailable",
            "errors": ["Activity agent not found"]
        }

    travel_details = state["travel_details"]

    # Check if travel details contain errors
    if "error" in travel_details:
        return {
            "activity_results": "Cannot search activities due to incomplete travel details",
            "errors": ["Travel details incomplete"]
        }

    try:
        # Prepare the prompt for the activity agent
        destination = travel_details.get('destination', 'Unknown')
        date_leaving = travel_details.get('date_leaving', 'Unknown')
        date_returning = travel_details.get('date_returning', 'Unknown')
        
        prompt = f"I need activity recommendations for {destination} from {date_leaving} to {date_returning}."

        # Call the activity agent
        result = await activity_agent.run(prompt)
        writer("✅ Activity recommendations retrieved successfully!\n")
        return {
            "activity_results": str(result.data) if hasattr(result, 'data') else str(result),
            "errors": []
        }
        
    except Exception as e:
        writer(f"❌ Error getting activity recommendations: {str(e)}\n")
        return {
            "activity_results": f"Activity search temporarily unavailable: {str(e)}",
            "errors": [f"Activity search failed: {str(e)}"]
        }


async def create_final_plan(state: TravelState, *, config) -> Dict[str, Any]:
    """Create a final travel plan based on all recommendations."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("📋 Creating your final travel plan...\n")

    if not final_planner_agent:
        writer("❌ Final planner agent not available\n")
        # Create a basic plan from available data
        travel_details = state["travel_details"]
        flight_results = state["flight_results"]
        hotel_results = state["hotel_results"]
        activity_results = state["activity_results"]
        
        basic_plan = f"""
🌟 TRAVEL PLAN SUMMARY

📍 Destination: {travel_details.get('destination', 'Unknown')}
📅 Dates: {travel_details.get('date_leaving', 'Unknown')} to {travel_details.get('date_returning', 'Unknown')}

✈️ FLIGHTS:
{flight_results}

🏨 ACCOMMODATIONS:
{hotel_results}

🎯 ACTIVITIES:
{activity_results}

⚠️ Note: This is a basic summary. Full planning service temporarily unavailable.
        """
        
        return {
            "final_plan": basic_plan.strip(),
            "errors": ["Final planner agent not found"]
        }

    travel_details = state["travel_details"]
    flight_results = state["flight_results"]
    hotel_results = state["hotel_results"]
    activity_results = state["activity_results"]
    errors = state.get("errors", [])

    try:
        # Prepare the prompt for the final planner agent
        prompt = f"""
        I'm planning a trip to {travel_details.get('destination', 'Unknown')} from {travel_details.get('origin', 'Unknown')} on {travel_details.get('date_leaving', 'Unknown')} and returning on {travel_details.get('date_returning', 'Unknown')}.

        Here are the flight recommendations:
        {flight_results}

        Here are the hotel recommendations:
        {hotel_results}

        Here are the activity recommendations:
        {activity_results}

        {"Note: Some services experienced errors: " + "; ".join(errors) if errors else ""}

        Please create a comprehensive travel plan based on these recommendations, organizing everything in a clear, actionable format.
        """

        # Call the final planner agent with streaming
        async with final_planner_agent.run_stream(prompt) as result:
            # Stream partial text as it arrives
            async for chunk in result.stream_text(delta=True):
                writer(chunk)

        # Get the final plan
        data = await result.get_output()
        writer("\n✅ Final travel plan created successfully!\n")
        
        return {
            "final_plan": str(data),
            "errors": errors
        }
        
    except Exception as e:
        writer(f"❌ Error creating final plan: {str(e)}\n")
        # Fallback to basic plan creation
        basic_plan = f"""
🌟 TRAVEL PLAN SUMMARY

📍 Destination: {travel_details.get('destination', 'Unknown')}
📅 Dates: {travel_details.get('date_leaving', 'Unknown')} to {travel_details.get('date_returning', 'Unknown')}

✈️ FLIGHTS:
{flight_results}

🏨 ACCOMMODATIONS:
{hotel_results}

🎯 ACTIVITIES:
{activity_results}

❌ Error creating detailed plan: {str(e)}
        """
        
        return {
            "final_plan": basic_plan.strip(),
            "errors": errors + [f"Final planning failed: {str(e)}"]
        }


def route_after_info_gathering(state: TravelState):
    """Determine what to do after gathering information."""
    travel_details = state["travel_details"]
    
    # Check for errors in travel details
    if "error" in travel_details:
        return "get_next_user_message"

    # Check if all details are given (this depends on your TravelDetails structure)
    all_details_given = travel_details.get("all_details_given", True)  # Default to True for now
    
    # You might want to check for specific required fields:
    required_fields = ['origin', 'destination', 'date_leaving', 'date_returning']
    has_required_fields = all(field in travel_details for field in required_fields)
    
    if not all_details_given or not has_required_fields:
        return "get_next_user_message"

    # If all details are given, proceed to parallel recommendations
    return ["get_flight_recommendations", "get_hotel_recommendations", "get_activity_recommendations"]


async def get_next_user_message(state: TravelState, *, config):
    """Get additional input from the user."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("🔄 I need some additional information to continue planning your trip...\n")

    # In a real application, this would wait for user input
    # For testing, we'll simulate getting additional info
    value = interrupt({"message": "Please provide more details about your travel plans."})

    return {
        "user_input": value
    }


def build_travel_agent_graph():
    """Build and return the travel agent graph."""
    # Create the graph with our state
    graph = StateGraph(TravelState)

    # Add nodes
    graph.add_node("gather_info", gather_info)
    graph.add_node("get_next_user_message", get_next_user_message)
    graph.add_node("get_flight_recommendations", get_flight_recommendations)
    graph.add_node("get_hotel_recommendations", get_hotel_recommendations)
    graph.add_node("get_activity_recommendations", get_activity_recommendations)
    graph.add_node("create_final_plan", create_final_plan)

    # Add edges
    graph.add_edge(START, "gather_info")

    # Conditional edge after info gathering
    graph.add_conditional_edges(
        "gather_info",
        route_after_info_gathering,
        ["get_next_user_message", "get_flight_recommendations", "get_hotel_recommendations",
         "get_activity_recommendations"]
    )

    # After getting a user message, route back to info gathering
    graph.add_edge("get_next_user_message", "gather_info")

    # Connect all recommendation nodes to the final planning node
    graph.add_edge("get_flight_recommendations", "create_final_plan")
    graph.add_edge("get_hotel_recommendations", "create_final_plan")
    graph.add_edge("get_activity_recommendations", "create_final_plan")

    # Connect final planning to END
    graph.add_edge("create_final_plan", END)

    # Compile the graph with memory
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Create the travel agent graph
travel_agent_graph = build_travel_agent_graph()


async def run_travel_agent_simple(user_input: str):
    """Simple version for testing."""
    # Generate a unique thread ID
    thread_id = str(uuid.uuid4())

    # Initialize the state with user input
    initial_state = {
        'thread_id': thread_id,
        "user_input": user_input,
        "messages": [],
        "travel_details": {},
        "preferred_airlines": [],
        "hotel_amenities": ["Wi-Fi", "Breakfast"],
        "budget_level": "medium",
        "flight_results": "",
        "hotel_results": "",
        "activity_results": "",
        "final_plan": "",
        "errors": []
    }

    # Configuration with thread_id for the checkpointer
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Run the graph
        result = await travel_agent_graph.ainvoke(initial_state, config=config)
        # ⚠️ Corrected: Return the plan and errors as a tuple
        return result.get("final_plan", "No plan generated"), result.get("errors", [])
    except Exception as e:
        # ⚠️ Corrected: Return the error message and errors as a tuple
        return f"Error running travel agent: {str(e)}", [str(e)]


async def run_travel_agent_with_streaming(user_input: str):
    """Run the travel agent with streaming output."""
    thread_id = str(uuid.uuid4())

    initial_state = {
        'thread_id': thread_id,
        "user_input": user_input,
        "messages": [],
        "travel_details": {},
        "preferred_airlines": [],
        "hotel_amenities": ["Wi-Fi", "Breakfast"],
        "budget_level": "medium",
        "flight_results": "",
        "hotel_results": "",
        "activity_results": "",
        "final_plan": "",
        "errors": []
    }

    config = {"configurable": {"thread_id": thread_id}}

    print(f"🚀 Starting travel planning for: {user_input}")
    print("=" * 60)

    final_result = None
    errors = []
    
    try:
        async for event in travel_agent_graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in event.items():
                print(f"🔄 Processing: {node_name}")
                if node_name == "create_final_plan":
                    if "final_plan" in update:
                        final_result = update["final_plan"]
                    if "errors" in update:
                        errors.extend(update["errors"])
    except Exception as e:
        print(f"❌ Streaming failed: {e}")
        # Fallback to simple execution
        final_result, errors = await run_travel_agent_simple(user_input)

    return final_result, errors


async def main():
    """Main function for testing."""
    # Example user input with corrected date format
    user_input = "I want to plan a trip from New York to Paris from 2025-09-15 to 2025-09-22. My budget for hotels is $300 per night."

    try:
        final_plan, errors = await run_travel_agent_with_streaming(user_input)
    except Exception as e:
        print(f"Error: {e}")
        final_plan, errors = await run_travel_agent_simple(user_input)

    # Print the results
    print("\n" + "=" * 60)
    print("🎯 FINAL TRAVEL PLAN:")
    print("=" * 60)
    print(final_plan if final_plan else "No final plan was generated.")
    
    if errors:
        print("\n" + "⚠️" * 20)
        print("ERRORS ENCOUNTERED:")
        for error in errors:
            print(f"❌ {error}")


# Example usage
if __name__ == "__main__":
    asyncio.run(main())
