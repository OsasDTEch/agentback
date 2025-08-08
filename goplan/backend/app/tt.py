import streamlit as st
import asyncio
import uuid
from typing import Dict, Any, List
import time
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
import sys
import os
from agent_graph import travel_agent_graph


def initialize_streamlit_app():
    """Initialize Streamlit app configuration with a clean, modern design."""
    st.set_page_config(
        page_title="🌍 AI Travel Planner",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for a modern, clean design with a new color palette
    st.markdown("""
    <style>
    /* Main body styling */
    body {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }

    /* Header styling with a modern gradient */
    .main-header {
        background: linear-gradient(90deg, #3a506b 0%, #1c2a39 100%);
        padding: 2.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }

    .main-header h1 {
        color: white;
        text-align: center;
        margin: 0;
        font-weight: 700;
        letter-spacing: 1px;
    }

    .main-header p {
        color: rgba(255, 255, 255, 0.8);
        text-align: center;
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
    }

    /* Stylish status box for progress updates */
    .status-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #007bff;
        background-color: #f8f9fa;
        transition: transform 0.2s ease-in-out;
    }

    .status-box strong {
        color: #007bff;
    }

    /* Chat message cards with different styles for clarity */
    .chat-message {
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transition: transform 0.2s ease-in-out;
    }

    .chat-message:hover {
        transform: translateY(-2px);
    }

    .user-message {
        background-color: #8f9db0;
        border-left: 4px solid #495057;
    }

    .agent-message {
        background-color: #7499bb ;
        border-left: 4px solid #20c997;
    }

    .system-message {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
    }

    /* Button and input styling */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }

    .stTextArea label {
        font-size: 1.1rem;
        font-weight: bold;
    }

    .stTextArea {
        border-radius: 8px;
    }

    /* Sidebar styling */
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
        border-right: 1px solid #e9ecef;
    }

    </style>
    """, unsafe_allow_html=True)


def display_header():
    """Display the main header with a gradient and a subtitle."""
    st.markdown("""
    <div class="main-header">
        <h1>🌍 AI Travel Planner</h1>
        <p>Your intelligent assistant for planning the perfect trip</p>
    </div>
    """, unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    if 'current_thread_id' not in st.session_state:
        st.session_state.current_thread_id = str(uuid.uuid4())

    if 'travel_state' not in st.session_state:
        st.session_state.travel_state = None

    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False

    if 'awaiting_user_input' not in st.session_state:
        st.session_state.awaiting_user_input = False

    if 'graph_config' not in st.session_state:
        st.session_state.graph_config = {
            "configurable": {"thread_id": st.session_state.current_thread_id}
        }

    if 'travel_agent_graph' not in st.session_state:
        # Initialize your graph here
         st.session_state.travel_agent_graph = travel_agent_graph


def display_sidebar():
    """Display sidebar with preferences and controls."""
    with st.sidebar:
        st.markdown("## 🎛️ Travel Preferences")

        # User preferences
        preferred_airlines = st.multiselect(
            "Preferred Airlines",
            ["Delta", "American Airlines", "United", "JetBlue", "Southwest", "Alaska Airlines"],
            default=[]
        )

        hotel_amenities = st.multiselect(
            "Hotel Amenities",
            ["WiFi", "Pool", "Gym", "Spa", "Restaurant", "Room Service", "Pet Friendly"],
            default=["WiFi"]
        )

        budget_level = st.selectbox(
            "Budget Level",
            ["budget", "medium", "luxury"],
            index=1
        )

        # Update session state with preferences
        st.session_state.preferred_airlines = preferred_airlines
        st.session_state.hotel_amenities = hotel_amenities
        st.session_state.budget_level = budget_level

        st.markdown("---")

        # Session controls
        if st.button("🔄 New Planning Session", type="secondary"):
            st.session_state.current_thread_id = str(uuid.uuid4())
            st.session_state.graph_config = {
                "configurable": {"thread_id": st.session_state.current_thread_id}
            }
            st.session_state.messages = []
            st.session_state.travel_state = None
            st.session_state.is_processing = False
            st.session_state.awaiting_user_input = False
            st.rerun()

        # Display current session info
        st.markdown("### 📊 Session Info")
        st.text(f"Thread ID: {st.session_state.current_thread_id[:8]}...")
        st.text(f"Messages: {len(st.session_state.messages)}")


def display_chat_messages():
    """Display chat messages in the main area."""
    st.markdown("## 💬 Travel Planning Chat")

    # Display existing messages
    for message in st.session_state.messages:
        message_type = message.get("type", "user")
        content = message.get("content", "")

        if message_type == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>🧑 You:</strong><br>
                {content}
            </div>
            """, unsafe_allow_html=True)

        elif message_type == "agent":
            st.markdown(f"""
            <div class="chat-message agent-message">
                <strong>🤖 Travel Agent:</strong><br>
                {content}
            </div>
            """, unsafe_allow_html=True)

        elif message_type == "system":
            st.markdown(f"""
            <div class="chat-message system-message">
                <strong>📋 System:</strong><br>
                {content}
            </div>
            """, unsafe_allow_html=True)


def handle_user_input():
    """Handle user input and process with the travel agent."""
    # Create input area
    col1, col2 = st.columns([4, 1])

    with col1:
        user_input = st.text_area(
            "Enter your travel request:",
            placeholder="e.g., I want to plan a trip from New York to Paris from 2025-09-15 to 2025-09-22",
            height=100,
            key="user_input",
            disabled=st.session_state.is_processing
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        send_button = st.button(
            "🚀 Send",
            type="primary",
            disabled=st.session_state.is_processing or not user_input.strip()
        )

        if st.session_state.is_processing:
            st.button("⏹️ Stop", disabled=True)

    return user_input, send_button


async def run_travel_agent_async(user_input: str):
    """Run the travel agent asynchronously with proper streaming."""
    try:
        # Initialize state
        initial_state = {
            'thread_id': st.session_state.current_thread_id,
            "user_input": user_input,
            "messages": [],
            "travel_details": {},
            "preferred_airlines": st.session_state.get('preferred_airlines', []),
            "hotel_amenities": st.session_state.get('hotel_amenities', []),
            "budget_level": st.session_state.get('budget_level', 'medium'),
            "flight_results": "",
            "hotel_results": "",
            "activity_results": "",
            "final_plan": ""
        }

        # Create status container for real-time updates
        status_container = st.empty()
        progress_bar = st.progress(0)

        # Simulate the graph execution with streaming
        # In practice, replace this with your actual graph execution

        steps = [
            ("gather_info", "🔍 Gathering travel information..."),
            ("get_flight_recommendations", "✈️ Finding flight options..."),
            ("get_hotel_recommendations", "🏨 Searching for hotels..."),
            ("get_activity_recommendations", "🎭 Discovering activities..."),
            ("create_final_plan", "📝 Creating your travel plan...")
        ]

        for i, (step_name, step_desc) in enumerate(steps):
            status_container.markdown(f"""
            <div class="status-box">
                <strong>{step_desc}</strong>
            </div>
            """, unsafe_allow_html=True)

            progress_bar.progress((i + 1) / len(steps))

            # Add artificial delay for demo (remove in production)
            await asyncio.sleep(1)

            # Check if we need user input (interrupt handling)
            if step_name == "gather_info" and "more information needed" in user_input.lower():
                st.session_state.awaiting_user_input = True
                status_container.markdown("""
                <div class="status-box">
                    <strong>🔄 Additional information needed...</strong><br>
                    Please provide more details about your travel preferences.
                </div>
                """, unsafe_allow_html=True)
                return "interrupt_for_more_info"

        # Simulate final plan generation
        final_plan = f"""
        # 🌍 Your Personalized Travel Plan

        ## Trip Summary
        - **Destination**: Paris (based on your request)
        - **Duration**: Week-long adventure
        - **Budget Level**: {st.session_state.get('budget_level', 'medium').title()}

        ## ✈️ Flight Recommendations
        - Outbound: Premium economy options available
        - Return: Flexible dates for better pricing
        - Airlines: {', '.join(st.session_state.get('preferred_airlines', ['Major carriers']))}

        ## 🏨 Hotel Recommendations
        - Boutique hotels in central Paris
        - Amenities: {', '.join(st.session_state.get('hotel_amenities', ['Standard amenities']))}
        - Location: Walking distance to major attractions

        ## 🎭 Activity Recommendations
        - Louvre Museum (skip-the-line tickets)
        - Eiffel Tower sunset viewing
        - Seine River cruise
        - Montmartre walking tour

        ## 💡 Pro Tips
        - Book flights 2-3 months in advance
        - Consider museum pass for savings
        - Try local bistros for authentic experience

        *Plan generated for thread: {st.session_state.current_thread_id[:8]}...*
        """

        status_container.success("✅ Travel plan completed successfully!")
        progress_bar.progress(1.0)

        return final_plan

    except Exception as e:
        st.error(f"Error processing travel request: {str(e)}")
        return None


def run_travel_agent_sync(user_input: str):
    """Synchronous wrapper for the async travel agent."""
    try:
        # Create new event loop for this execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run the async function
        result = loop.run_until_complete(run_travel_agent_async(user_input))
        return result

    except Exception as e:
        st.error(f"Error in travel agent execution: {str(e)}")
        return None

    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass


def main():
    """Main Streamlit application."""
    # Initialize app
    initialize_streamlit_app()
    display_header()
    initialize_session_state()

    # Create main layout
    col1, col2 = st.columns([3, 1])

    with col2:
        display_sidebar()

    with col1:
        # Display chat messages
        display_chat_messages()

        # Handle user input
        user_input, send_button = handle_user_input()

        # Process user input
        if send_button and user_input.strip():
            # Add user message to chat
            st.session_state.messages.append({
                "type": "user",
                "content": user_input,
                "timestamp": time.time()
            })

            # Set processing state
            st.session_state.is_processing = True

            # Rerun to show user message and processing state
            st.rerun()

        # Process the request if we're in processing state
        if st.session_state.is_processing and st.session_state.messages:
            last_message = st.session_state.messages[-1]
            if last_message["type"] == "user":
                with st.spinner("Processing your travel request..."):
                    # Run the travel agent
                    result = run_travel_agent_sync(last_message["content"])

                    if result:
                        if result == "interrupt_for_more_info":
                            # Handle interrupt case
                            st.session_state.messages.append({
                                "type": "system",
                                "content": "Please provide additional information to continue planning your trip.",
                                "timestamp": time.time()
                            })
                            st.session_state.awaiting_user_input = True
                        else:
                            # Add agent response
                            st.session_state.messages.append({
                                "type": "agent",
                                "content": result,
                                "timestamp": time.time()
                            })

                    # Reset processing state
                    st.session_state.is_processing = False
                    st.rerun()

        # Show status if awaiting user input
        if st.session_state.awaiting_user_input:
            st.info(
                "💭 I need some additional information to continue planning your trip. Please provide more details above.")

        # Quick start examples
        if not st.session_state.messages:
            st.markdown("### 💡 Quick Start Examples")

            examples = [
                "Plan a romantic weekend in Paris from 2025-12-15 to 2025-12-17",
                "Family vacation to Disney World for 5 days in summer 2025",
                "Business trip to Tokyo with luxury hotels from 2025-10-01 to 2025-10-05",
                "Budget backpacking trip across Europe for 2 weeks"
            ]

            for example in examples:
                if st.button(f"� {example}", key=f"example_{hash(example)}"):
                    st.session_state.messages.append({
                        "type": "user",
                        "content": example,
                        "timestamp": time.time()
                    })
                    st.session_state.is_processing = True
                    st.rerun()


if __name__ == "__main__":
    main()
