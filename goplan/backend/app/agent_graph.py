import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from typing import Annotated, Dict, List, Any
from typing_extensions import TypedDict
from langgraph.types import interrupt
from pydantic import ValidationError
from dataclasses import dataclass
import logfire
import asyncio
import sys
import os

# Import the message classes from Pydantic AI
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter
)
from goplan.backend.app.agents.info_gathering_agent import info_gathering_agent, TravelDetails
from goplan.backend.app.agents.flight_agent import flight_agent, FlightDeps
from goplan.backend.app.agents.hotel_agent import hotel_agent, HotelDeps
from goplan.backend.app.agents.activity_agent import activity_agent
from goplan.backend.app.agents.final_planner_agent import final_planner_agent


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


# Node functions for the graph
# Info gathering node
async def gather_info(state: TravelState, *, config) -> Dict[str, Any]:
    """Gather necessary travel information from the user."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        # Fallback if stream writer is not available
        writer = lambda x: print(x, end='', flush=True)
    user_input = state["user_input"]

    # Get the message history into the format for Pydantic AI
    message_history: list[ModelMessage] = []
    for message_row in state.get('messages', []):
        message_history.extend(ModelMessagesTypeAdapter.validate_json(message_row))

    # Call the info gathering agent
    async with info_gathering_agent.run_stream(user_input, message_history=message_history) as result:
        curr_response = ""
        travel_details = None

        async for message, last in result.stream_structured(debounce_by=0.01):
            try:
                # Use the new method name
                travel_details = await result.validate_structured_output(
                    message,
                    allow_partial=not last
                )
                if last and not travel_details.response:
                    raise Exception("Incorrect travel details returned by the agent.")
            except ValidationError as e:
                continue

            if travel_details and travel_details.response:
                new_content = travel_details.response[len(curr_response):]
                if new_content:
                    writer(new_content)
                curr_response = travel_details.response

    # Use the new method name
    data = await result.get_output()
    return {
        "travel_details": data.model_dump(),
        "messages": [result.new_messages_json()]
    }


async def get_flight_recommendations(state: TravelState, *, config) -> Dict[str, Any]:
    """Get flight recommendations based on travel details."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("\n#### Getting flight recommendations...\n")

    travel_details = state["travel_details"]
    preferred_airlines = state.get('preferred_airlines', [])

    # Create flight dependencies
    flight_dependencies = FlightDeps(preferred_airlines=preferred_airlines)

    # Prepare the prompt for the flight agent
    prompt = f"I need flight recommendations from {travel_details['origin']} to {travel_details['destination']} on {travel_details['date_leaving']}. Return flight on {travel_details['date_returning']}."

    try:
        # Call the flight agent
        result = await flight_agent.run(prompt, deps=flight_dependencies)
        writer("✅ Flight recommendations retrieved successfully!\n")
        return {"flight_results": result.data}
    except Exception as e:
        writer(f"❌ Error getting flight recommendations: {str(e)}\n")
        return {"flight_results": f"Flight search temporarily unavailable: {str(e)}"}


async def get_hotel_recommendations(state: TravelState, *, config) -> Dict[str, Any]:
    """Get hotel recommendations based on travel details."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("\n#### Getting hotel recommendations...\n")

    travel_details = state["travel_details"]
    hotel_amenities = state.get('hotel_amenities', [])
    budget_level = state.get('budget_level', 'medium')

    # Create hotel dependencies
    hotel_dependencies = HotelDeps(
        hotel_amenities=hotel_amenities,
        budget_level=budget_level
    )

    # Prepare the prompt for the hotel agent
    prompt = f"I need hotel recommendations in {travel_details['destination']} from {travel_details['date_leaving']} to {travel_details['date_returning']} with a maximum price of ${travel_details.get('max_hotel_price', '200')} per night."

    try:
        # Call the hotel agent
        result = await hotel_agent.run(prompt, deps=hotel_dependencies)
        writer("✅ Hotel recommendations retrieved successfully!\n")
        return {"hotel_results": result.data}
    except Exception as e:
        writer(f"❌ Error getting hotel recommendations: {str(e)}\n")
        return {"hotel_results": f"Hotel search temporarily unavailable: {str(e)}"}


async def get_activity_recommendations(state: TravelState, *, config) -> Dict[str, Any]:
    """Get activity recommendations based on travel details."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("\n#### Getting activity recommendations...\n")

    travel_details = state["travel_details"]

    # Prepare the prompt for the activity agent
    prompt = f"I need activity recommendations for {travel_details['destination']} from {travel_details['date_leaving']} to {travel_details['date_returning']}."

    try:
        # Call the activity agent
        result = await activity_agent.run(prompt)
        writer("✅ Activity recommendations retrieved successfully!\n")
        return {"activity_results": result.data}
    except Exception as e:
        writer(f"❌ Error getting activity recommendations: {str(e)}\n")
        return {"activity_results": f"Activity search temporarily unavailable: {str(e)}"}


# Final planning node
async def create_final_plan(state: TravelState, *, config) -> Dict[str, Any]:
    """Create a final travel plan based on all recommendations."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("\n#### Creating your final travel plan...\n")

    travel_details = state["travel_details"]
    flight_results = state["flight_results"]
    hotel_results = state["hotel_results"]
    activity_results = state["activity_results"]

    # Prepare the prompt for the final planner agent
    prompt = f"""
    I'm planning a trip to {travel_details['destination']} from {travel_details['origin']} on {travel_details['date_leaving']} and returning on {travel_details['date_returning']}.

    Here are the flight recommendations:
    {flight_results}

    Here are the hotel recommendations:
    {hotel_results}

    Here are the activity recommendations:
    {activity_results}

    Please create a comprehensive travel plan based on these recommendations.
    """

    try:
        # Call the final planner agent
        async with final_planner_agent.run_stream(prompt) as result:
            # Stream partial text as it arrives
            async for chunk in result.stream_text(delta=True):
                writer(chunk)

        # Return the final plan
        data = await result.get_output()
        return {"final_plan": data}
    except Exception as e:
        writer(f"❌ Error creating final plan: {str(e)}\n")
        return {"final_plan": f"Error creating plan: {str(e)}"}


def route_after_info_gathering(state: TravelState):
    """Determine what to do after gathering information."""
    travel_details = state["travel_details"]

    # If all details are not given, we need more information
    if not travel_details.get("all_details_given", False):
        return "get_next_user_message"

    # If all details are given, we can proceed to parallel recommendations
    return ["get_flight_recommendations", "get_hotel_recommendations", "get_activity_recommendations"]


async def get_next_user_message(state: TravelState, *, config):
    """Get additional input from the user."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda x: print(x, end='', flush=True)

    writer("\n🔄 I need some additional information to continue planning your trip...\n")

    value = interrupt({})

    # Set the user's latest message for the LLM to continue the conversation
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

    # After getting a user message, route back to the info gathering agent
    graph.add_edge("get_next_user_message", "gather_info")

    # Connect all recommendation nodes to the final planning node
    graph.add_edge("get_flight_recommendations", "create_final_plan")
    graph.add_edge("get_hotel_recommendations", "create_final_plan")
    graph.add_edge("get_activity_recommendations", "create_final_plan")

    # Connect final planning to END
    graph.add_edge("create_final_plan", END)

    # Compile the graph
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Create the travel agent graph
travel_agent_graph = build_travel_agent_graph()


async def run_travel_agent(user_input: str):
    """Run the travel agent with the given user input."""
    # Generate a unique thread ID
    thread_id = str(uuid.uuid4())

    # Initialize the state with user input
    initial_state = {
        'thread_id': thread_id,
        "user_input": user_input,
        "messages": [],
        "travel_details": {},
        "preferred_airlines": [],
        "hotel_amenities": [],
        "budget_level": "medium",
        "flight_results": "",
        "hotel_results": "",
        "activity_results": "",
        "final_plan": ""
    }

    # Configuration with thread_id for the checkpointer
    config = {"configurable": {"thread_id": thread_id}}

    # Run the graph with config and collect streaming output
    final_result = None
    async for event in travel_agent_graph.astream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in event.items():
            if node_name == "create_final_plan" and "final_plan" in update:
                final_result = update["final_plan"]

    return final_result


async def run_travel_agent_simple(user_input: str):
    """Simple version without complex streaming."""
    # Generate a unique thread ID
    thread_id = str(uuid.uuid4())

    # Initialize the state with user input
    initial_state = {
        'thread_id': thread_id,
        "user_input": user_input,
        "messages": [],
        "travel_details": {},
        "preferred_airlines": [],
        "hotel_amenities": [],
        "budget_level": "medium",
        "flight_results": "",
        "hotel_results": "",
        "activity_results": "",
        "final_plan": ""
    }

    # Configuration with thread_id for the checkpointer
    config = {"configurable": {"thread_id": thread_id}}

    # Run the graph with config
    result = await travel_agent_graph.ainvoke(initial_state, config=config)

    # Return the final plan
    return result.get("final_plan", "No plan generated")


async def run_travel_agent_with_streaming(user_input: str):
    """Run the travel agent with streaming output for better user experience."""
    # Generate a unique thread ID
    thread_id = str(uuid.uuid4())

    # Initialize the state with user input
    initial_state = {
        'thread_id': thread_id,
        "user_input": user_input,
        "messages": [],
        "travel_details": {},
        "preferred_airlines": [],
        "hotel_amenities": [],
        "budget_level": "medium",
        "flight_results": "",
        "hotel_results": "",
        "activity_results": "",
        "final_plan": ""
    }

    # Configuration with thread_id for the checkpointer
    config = {"configurable": {"thread_id": thread_id}}

    print(f"🚀 Starting travel planning for: {user_input}")
    print("=" * 60)

    # Run the graph with config and stream updates
    final_result = None
    try:
        async for event in travel_agent_graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in event.items():
                print(f"🔄 Processing: {node_name}")
                if node_name == "create_final_plan" and "final_plan" in update:
                    final_result = update["final_plan"]
    except Exception as e:
        print(f"❌ Streaming failed, falling back to simple execution: {e}")
        # Fallback to simple execution
        result = await travel_agent_graph.ainvoke(initial_state, config=config)
        final_result = result.get("final_plan", "No plan generated")

    return final_result


async def main():
    # Example user input with corrected date format (2025 instead of 2024)
    user_input = "I want to plan a trip from New York to Paris from 2025-09-15 to 2025-09-22. My max budget for a hotel is $2000 per night."

    # Try streaming first, fallback to simple if needed
    try:
        final_plan = await run_travel_agent_with_streaming(user_input)
    except Exception as e:
        print(f"Streaming failed: {e}")
        print("Falling back to simple execution...")
        final_plan = await run_travel_agent_simple(user_input)

    # Print the final plan
    print("\n" + "=" * 60)
    print("🎯 FINAL TRAVEL PLAN:")
    print("=" * 60)
    print(final_plan if final_plan else "No final plan was generated.")


# Example usage
if __name__ == "__main__":
    asyncio.run(main())