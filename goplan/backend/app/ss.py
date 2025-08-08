import streamlit as st
import requests
from datetime import datetime, date
import json

# Page configuration
st.set_page_config(
    page_title="Trip Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 3rem;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 3rem;
    }
    .section-header {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
        margin-top: 30px;
        margin-bottom: 20px;
    }
    .stSelectbox > div > div {
        background-color: #1a1a1a !important;
        color: white !important;
    }
    .stSelectbox > div > div > div {
        background-color: #1a1a1a !important;
        color: white !important;
    }
    .trip-result {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 20px 0;
    }
    .error-box {
        background-color: #fee;
        border: 1px solid #fcc;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">✈️ AI Trip Planner</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Plan your perfect getaway with AI-powered recommendations</p>',
            unsafe_allow_html=True)

# Sidebar for additional options
with st.sidebar:
    st.markdown("### 🎯 Trip Preferences")

    # Fixed API URL (hidden from user)
    api_url = "http://127.0.0.1:8000/plan-trip"

    # Advanced preferences
    st.markdown("#### Advanced Options")
    preferred_airlines = st.multiselect(
        "Preferred Airlines",
        ["American Airlines", "Delta", "United", "Southwest", "JetBlue", "Alaska Airlines"],
        help="Select your preferred airlines (optional)"
    )

    hotel_amenities = st.multiselect(
        "Hotel Amenities",
        ["WiFi", "Pool", "Gym", "Spa", "Pet-friendly", "Business Center", "Restaurant", "Room Service"],
        help="Select desired hotel amenities"
    )

    # Trip type
    trip_type = st.selectbox(
        "Trip Type",
        ["Leisure", "Business", "Adventure", "Family", "Romantic", "Solo Travel"],
        help="What type of trip are you planning?"
    )

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<h3 class="section-header">📝 Trip Details</h3>', unsafe_allow_html=True)

    # Trip details input
    user_input = st.text_area(
        "Describe your ideal trip",
        placeholder="Example: I want to visit Paris for 5 days in March. I love museums, good food, and historic sites. Looking for mid-range accommodations in a central location.",
        height=120,
        help="Be as specific as possible - destinations, duration, interests, special requirements, etc."
    )

    # Date inputs
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.date_input(
            "Departure Date",
            value=datetime.now().date(),
            min_value=datetime.now().date(),
            help="When do you plan to start your trip?"
        )

    with col_date2:
        end_date = st.date_input(
            "Return Date",
            value=datetime.now().date(),
            min_value=start_date,
            help="When do you plan to return?"
        )

    # Budget and group size
    col_budget1, col_budget2 = st.columns(2)
    with col_budget1:
        budget_level = st.selectbox(
            "Budget Level",
            ["low", "medium", "high"],
            index=1,
            help="Low: Budget-conscious, Medium: Moderate spending, High: Premium experience"
        )

    with col_budget2:
        group_size = st.number_input(
            "Group Size",
            min_value=1,
            max_value=20,
            value=2,
            help="Number of travelers"
        )

with col2:
    st.markdown('<h3 class="section-header">💰 Budget Breakdown</h3>', unsafe_allow_html=True)

    # Budget indicators
    budget_descriptions = {
        "low": {
            "icon": "💵",
            "description": "Budget-friendly options\n- Hostels/Budget hotels\n- Public transport\n- Local eateries",
            "color": "#28a745"
        },
        "medium": {
            "icon": "💳",
            "description": "Balanced comfort & cost\n- 3-star hotels\n- Mix of transport options\n- Mid-range restaurants",
            "color": "#ffc107"
        },
        "high": {
            "icon": "💎",
            "description": "Premium experience\n- Luxury hotels\n- Private transport\n- Fine dining",
            "color": "#dc3545"
        }
    }

    current_budget = budget_descriptions[budget_level]
    st.markdown(f"""
    <div style="background-color: {current_budget['color']}20; padding: 15px; border-radius: 10px; border-left: 4px solid {current_budget['color']}">
        <h4>{current_budget['icon']} {budget_level.title()} Budget</h4>
        <p style="white-space: pre-line; margin: 0;">{current_budget['description']}</p>
    </div>
    """, unsafe_allow_html=True)

    # Trip duration
    if start_date and end_date:
        duration = (end_date - start_date).days
        st.metric("Trip Duration", f"{duration} days")
        st.metric("Total Travelers", f"{group_size} people")

# Plan Trip Button
st.markdown('<h3 class="section-header">🚀 Generate Your Trip Plan</h3>', unsafe_allow_html=True)

# Validation
if st.button("🎯 Plan My Trip", type="primary", use_container_width=True):
    if not user_input.strip():
        st.error("Please describe your trip details before planning!")
    elif start_date >= end_date:
        st.error("Return date must be after departure date!")
    else:
        # Prepare payload
        payload = {
            "user_input": user_input,
            "budget_level": budget_level,
            "preferred_airlines": preferred_airlines,
            "hotel_amenities": hotel_amenities,
            "trip_type": trip_type,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "group_size": group_size,
            "duration_days": (end_date - start_date).days
        }

        # Show loading state
        with st.spinner("🔄 Planning your perfect trip..."):
            try:
                response = requests.post(api_url, json=payload)
                response.raise_for_status()
                data = response.json()

                # Cool Success Display
                st.markdown("""
                <div style="background: linear-gradient(45deg, #667eea, #764ba2); padding: 30px; border-radius: 20px; margin: 20px 0;">
                    <div style="text-align: center; color: white;">
                        <h2 style="margin: 0; font-size: 2.5em;">🎉</h2>
                        <h3 style="margin: 10px 0; color: #fff;">Your Adventure Awaits!</h3>
                        <p style="margin: 0; opacity: 0.9;">AI has crafted your perfect journey</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Cool response display
                if isinstance(data, dict):
                    # Create a stylish container for the trip plan
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 2px; border-radius: 15px; margin: 20px 0;">
                        <div style="background: #1a1a2e; padding: 25px; border-radius: 13px;">
                    """, unsafe_allow_html=True)

                    # Display trip overview in cards
                    if "destination" in data:
                        st.markdown(f"""
                        <div style="background: linear-gradient(45deg, #ff6b6b, #ee5a24); padding: 20px; border-radius: 10px; margin: 15px 0; text-align: center;">
                            <h2 style="color: white; margin: 0;">🌍 {data["destination"]}</h2>
                        </div>
                        """, unsafe_allow_html=True)

                    # Itinerary display
                    if "itinerary" in data:
                        st.markdown("""
                        <div style="color: #00d4aa; font-size: 1.5em; margin: 20px 0; text-align: center;">
                            📅 Your Daily Adventure
                        </div>
                        """, unsafe_allow_html=True)

                        if isinstance(data["itinerary"], list):
                            for day, activities in enumerate(data["itinerary"], 1):
                                st.markdown(f"""
                                <div style="background: rgba(0, 212, 170, 0.1); border-left: 4px solid #00d4aa; padding: 15px; margin: 10px 0; border-radius: 0 10px 10px 0;">
                                    <h4 style="color: #00d4aa; margin: 0 0 10px 0;">Day {day}</h4>
                                    <p style="color: #e0e0e0; margin: 0; line-height: 1.6;">{activities}</p>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="background: rgba(0, 212, 170, 0.1); border-left: 4px solid #00d4aa; padding: 15px; margin: 10px 0; border-radius: 0 10px 10px 0;">
                                <p style="color: #e0e0e0; margin: 0; line-height: 1.6;">{data["itinerary"]}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    # Accommodations
                    if "accommodations" in data:
                        st.markdown(f"""
                        <div style="background: rgba(255, 107, 107, 0.1); border-left: 4px solid #ff6b6b; padding: 15px; margin: 15px 0; border-radius: 0 10px 10px 0;">
                            <h4 style="color: #ff6b6b; margin: 0 0 10px 0;">🏨 Where You'll Stay</h4>
                            <p style="color: #e0e0e0; margin: 0; line-height: 1.6;">{data["accommodations"]}</p>
                        </div>
                        """, unsafe_allow_html=True)

                    # Cost estimation
                    if "estimated_cost" in data:
                        st.markdown(f"""
                        <div style="background: linear-gradient(45deg, #f093fb, #f5576c); padding: 20px; border-radius: 10px; margin: 15px 0; text-align: center;">
                            <h3 style="color: white; margin: 0;">💰 Estimated Cost</h3>
                            <h2 style="color: white; margin: 10px 0; font-size: 2em;">{data["estimated_cost"]}</h2>
                        </div>
                        """, unsafe_allow_html=True)

                    # Display any other fields in a cool way
                    other_fields = {k: v for k, v in data.items() if
                                    k not in ["destination", "itinerary", "accommodations", "estimated_cost"]}
                    if other_fields:
                        st.markdown("""
                        <div style="color: #ffa726; font-size: 1.3em; margin: 20px 0; text-align: center;">
                            ✨ Additional Details
                        </div>
                        """, unsafe_allow_html=True)

                        for key, value in other_fields.items():
                            st.markdown(f"""
                            <div style="background: rgba(255, 167, 38, 0.1); border-left: 4px solid #ffa726; padding: 15px; margin: 10px 0; border-radius: 0 10px 10px 0;">
                                <h4 style="color: #ffa726; margin: 0 0 10px 0; text-transform: capitalize;">{key.replace('_', ' ')}</h4>
                                <p style="color: #e0e0e0; margin: 0; line-height: 1.6;">{value}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    st.markdown("</div></div>", unsafe_allow_html=True)

                else:
                    # Fallback for non-dict responses
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 25px; border-radius: 15px; color: white;">
                        <h3 style="margin-top: 0;">🎯 Your Trip Plan</h3>
                        <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; font-family: monospace;">
                            {str(data)}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            except requests.exceptions.ConnectionError:
                st.markdown("""
                <div style="background: linear-gradient(45deg, #e74c3c, #c0392b); padding: 20px; border-radius: 10px; text-align: center; color: white;">
                    <h3>🔌 Connection Lost</h3>
                    <p>Cannot reach the planning server. Make sure it's running!</p>
                </div>
                """, unsafe_allow_html=True)
            except requests.exceptions.HTTPError as e:
                st.markdown(f"""
                <div style="background: linear-gradient(45deg, #e74c3c, #c0392b); padding: 20px; border-radius: 10px; color: white;">
                    <h3>❌ Server Error</h3>
                    <p>HTTP {e.response.status_code}: Something went wrong on the server</p>
                    <details style="margin-top: 15px;">
                        <summary style="cursor: pointer;">🔧 Technical Details</summary>
                        <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 5px; margin-top: 10px; font-family: monospace; font-size: 0.9em;">
                            {e.response.text}
                        </div>
                    </details>
                </div>
                """, unsafe_allow_html=True)
            except requests.exceptions.RequestException as e:
                st.markdown(f"""
                <div style="background: linear-gradient(45deg, #e74c3c, #c0392b); padding: 20px; border-radius: 10px; color: white;">
                    <h3>❌ Request Failed</h3>
                    <p>Something went wrong while planning your trip</p>
                    <details style="margin-top: 15px;">
                        <summary style="cursor: pointer;">🔧 Technical Details</summary>
                        <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 5px; margin-top: 10px; font-family: monospace; font-size: 0.9em;">
                            {str(e)}
                        </div>
                    </details>
                </div>
                """, unsafe_allow_html=True)
            except json.JSONDecodeError:
                st.markdown("""
                <div style="background: linear-gradient(45deg, #e74c3c, #c0392b); padding: 20px; border-radius: 10px; text-align: center; color: white;">
                    <h3>📄 Invalid Response</h3>
                    <p>Server sent an invalid response. Please try again!</p>
                </div>
                """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🤖 Powered by AI Trip Planning | Made with ❤️ using Streamlit</p>
        <p><small>Tip: Be specific about your preferences for better recommendations!</small></p>
    </div>
    """,
    unsafe_allow_html=True
)