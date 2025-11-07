import streamlit as st
import googlemaps
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import json
import pandas as pd
import google.generativeai as genai
from utils.maps import MapsService
from utils.places import PlacesService
from utils.tolls import TollService
from utils.schedule import SchedulePlanner
from utils.fuel import FuelService
from utils.profiles import ProfileManager, UserProfile, VehicleProfile, UserPreferences
from utils.auth import AuthManager
from utils.llm import LLMService
import requests
import pydeck as pdk
from utils.trip_planner import TripPlanner

# Load environment variables
load_dotenv()

# Initialize Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.0-pro')

# Initialize services
maps_service = MapsService()
places_service = PlacesService()
toll_service = TollService()
schedule_planner = SchedulePlanner()
fuel_service = FuelService()
profile_manager = ProfileManager()
auth_manager = AuthManager()
llm_service = LLMService()

# Initialize trip planner
trip_planner = TripPlanner()

# Page configuration
st.set_page_config(
    page_title="India Road Trip Planner",
    page_icon="🚗",
    layout="wide"
)


# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_guest' not in st.session_state:
    st.session_state.is_guest = False
if 'show_auth_page' not in st.session_state:
    st.session_state.show_auth_page = False

# Authentication functions
def login(username: str, password: str) -> bool:
    return auth_manager.verify_user(username, password)

def register(username: str, password: str, email: str) -> bool:
    return auth_manager.register_user(username, password, email)

def get_sightseeing_spots(start_point, end_point, route_points):
    """Get sightseeing spots along the route using LLMService"""
    try:
        # Get spots from LLM service
        spots = llm_service.get_sightseeing_spots(start_point, end_point)
        
        # Get additional details for each spot
        for spot in spots:
            try:
                details = llm_service.get_spot_details(
                    spot['name'],
                    route_points[0],  # Use first point of route as reference
                    places_service,
                    maps_service
                )
                if details:
                    spot.update(details)
            except Exception as e:
                st.warning(f"Could not get details for {spot['name']}: {str(e)}")
                continue
        
        return spots
    except Exception as e:
        st.error(f"Error fetching sightseeing spots: {str(e)}")
        return []

# Main application logic
if not st.session_state.authenticated:
    if not st.session_state.show_auth_page:
        # Front page with login/signup buttons
        header_container = st.container()
        with header_container:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.title("🚗 India Road Trip Planner")
            with col2:
                if st.button("Login / Sign Up", key="header_auth_button"):
                    st.session_state.show_auth_page = True
                    st.rerun()

        # Main content area with app description
        st.markdown("""
        ## Plan Your Perfect Road Trip Across India
        
        Welcome to the India Road Trip Planner - your smart companion for planning unforgettable road trips across India! 
        Our app helps you create personalized road trip experiences with:
        
        🗺️ **Smart Route Planning**
        - Optimized routes for cars and bikes
        - Interactive maps 
        - Optimised stops and waypoints
        
        ⛽ **Cost Optimization**
        - Real-time fuel cost estimation
        - Toll cost calculation
        - Smart refueling stop suggestions
        
        🕒 **Time-Aware Planning**
        - Personalized driving schedules
        - Smart meal and rest stop suggestions
        - Hotel recommendations for overnight stays
        
        🍽️ **Travel Comfort**
        - Restaurant suggestions based on your schedule
        - Hotel recommendations for multi-day trips
        - Rest stop optimization
        
        Get started by logging in or creating an account to save your preferences and trip history!
        """)
    else:
        # Show login/register page
        st.title("🚗 India Road Trip Planner")
        
        # Back button to return to front page
        if st.button("← Back to Home", key="back_to_home"):
            st.session_state.show_auth_page = False
            st.rerun()
        
        # Create tabs for login and registration
        login_tab, register_tab = st.tabs(["Login", "Register"])
        
        with login_tab:
            # Split the login page into two columns
            login_col, guest_col = st.columns(2)
            
            # Login form in left column
            with login_col:
                st.markdown('<div class="auth-container">', unsafe_allow_html=True)
                st.subheader("Login to Your Account")
                login_username = st.text_input("Username", key="login_username")
                login_password = st.text_input("Password", type="password", key="login_password")
                
                if st.button("Login", key="login_form_button", use_container_width=True):
                    if trip_planner.login(login_username, login_password):
                        st.session_state.authenticated = True
                        st.session_state.username = login_username
                        st.session_state.is_guest = False
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Guest login in right column
            with guest_col:
                st.markdown('<div class="auth-container">', unsafe_allow_html=True)
                st.subheader("Continue as Guest")
                st.markdown("""
                Don't have an account? No problem! You can continue as a guest to:
                - Plan your road trip
                - Get route suggestions
                - Calculate costs
                
                Note: Your data won't be saved after you log out.
                """)
                if st.button("Guest Login", key="guest_login_button", use_container_width=True):
                    guest_username = trip_planner.guest_login()
                    st.session_state.authenticated = True
                    st.session_state.username = guest_username
                    st.session_state.is_guest = True
                    st.success("Logged in as guest!")
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        
        with register_tab:
            with st.container():
                st.markdown('<div class="auth-container">', unsafe_allow_html=True)
                st.subheader("Register")
                reg_username = st.text_input("Username", key="reg_username")
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input("Password", type="password", key="reg_password")
                reg_confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
                
                if st.button("Register", key="register_form_button"):
                    if reg_password != reg_confirm_password:
                        st.error("Passwords do not match")
                    elif trip_planner.register(reg_username, reg_password, reg_email):
                        st.success("Registration successful! Please login.")
                    else:
                        st.error("Username already exists")
                st.markdown('</div>', unsafe_allow_html=True)

else:
    # Show main application
    st.title("🚗 India Road Trip Planner")
    st.markdown("Plan your perfect road trip across India with optimized routes, smart stops, and cost estimates!")
    
    # Add logout button in sidebar
    with st.sidebar:
        if st.button("Logout", key="logout_button"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.is_guest = False
            st.rerun()
        
        # Show guest badge if user is a guest
        if st.session_state.is_guest:
            st.info("You are using a guest account. Your data won't be saved after logout.")
    
    # Sidebar for user inputs
    with st.sidebar:
        st.header("Trip Details")
        
        # Profile Management - Only show for registered users
        if not st.session_state.is_guest:
            st.subheader("Profile Management")
            
            # User Profile Selection
            user_profile_options = ["Select User Profile", "Create New User Profile", "No User Profile"]
            available_user_profiles = trip_planner.profile_manager.list_user_profiles()
            if available_user_profiles:
                user_profile_options = available_user_profiles + ["Create New User Profile", "No User Profile"]
            
            selected_user_profile = st.selectbox("User Profile", user_profile_options)
            
            if selected_user_profile == "Create New User Profile":
                user_profile_name = st.text_input("New User Profile Name")
                
                # User preferences
                st.subheader("Travel Preferences")
                driving_hours_start = st.time_input("Preferred Driving Start Time", datetime.strptime("06:00", "%H:%M").time())
                driving_hours_end = st.time_input("Preferred Driving End Time", datetime.strptime("19:00", "%H:%M").time())
                
                # Meal preferences
                st.subheader("Meal Preferences")
                breakfast_time = st.time_input("Breakfast Time", datetime.strptime("08:00", "%H:%M").time())
                lunch_time = st.time_input("Lunch Time", datetime.strptime("13:00", "%H:%M").time())
                dinner_time = st.time_input("Dinner Time", datetime.strptime("20:00", "%H:%M").time())
                
                if st.button("Save User Profile", key="save_user_profile"):
                    if user_profile_name:
                        user_preferences = UserPreferences(
                            driving_hours_start=driving_hours_start,
                            driving_hours_end=driving_hours_end,
                            breakfast_time=breakfast_time,
                            lunch_time=lunch_time,
                            dinner_time=dinner_time
                        )
                        
                        user_profile = UserProfile(
                            name=user_profile_name,
                            preferences=user_preferences
                        )
                        
                        if trip_planner.profile_manager.save_user_profile(user_profile_name, user_profile.to_dict()):
                            st.success(f"User profile '{user_profile_name}' saved successfully!")
                            st.rerun()
                        else:
                            st.error("Error saving user profile")
                    else:
                        st.error("Please enter a profile name")
            
            elif selected_user_profile != "No User Profile" and selected_user_profile != "Select User Profile":
                user_profile_data = trip_planner.profile_manager.load_user_profile(selected_user_profile)
                if user_profile_data:
                    user_preferences = UserPreferences.from_dict(user_profile_data['preferences'])
                    driving_hours_start = user_preferences.driving_hours_start
                    driving_hours_end = user_preferences.driving_hours_end
                    breakfast_time = user_preferences.breakfast_time
                    lunch_time = user_preferences.lunch_time
                    dinner_time = user_preferences.dinner_time
                else:
                    st.error("Error loading user profile")
            
            # Vehicle Profile Selection
            vehicle_profile_options = ["Select Vehicle Profile", "Create New Vehicle Profile", "No Vehicle Profile"]
            available_vehicle_profiles = trip_planner.profile_manager.list_vehicle_profiles()
            if available_vehicle_profiles:
                vehicle_profile_options = available_vehicle_profiles + ["Create New Vehicle Profile", "No Vehicle Profile"]
            
            selected_vehicle_profile = st.selectbox("Vehicle Profile", vehicle_profile_options)
            
            if selected_vehicle_profile == "Create New Vehicle Profile":
                vehicle_profile_name = st.text_input("New Vehicle Profile Name")
                
                # Vehicle profile
                st.subheader("Vehicle Details")
                vehicle_type = st.selectbox("Vehicle Type", ["Car", "Bike"])
                fuel_type = st.selectbox("Fuel Type", ["Petrol", "Diesel"])
                mileage = st.number_input("Mileage (km/l)", min_value=1.0, value=20.0)
                tank_size = st.number_input("Tank Size (liters)", min_value=1.0, value=40.0)
                
                if st.button("Save Vehicle Profile", key="save_vehicle_profile"):
                    if vehicle_profile_name:
                        vehicle_profile = VehicleProfile(
                            name=vehicle_profile_name,
                            vehicle_type=vehicle_type,
                            fuel_type=fuel_type,
                            mileage=mileage,
                            tank_size=tank_size
                        )
                        
                        if trip_planner.profile_manager.save_vehicle_profile(vehicle_profile_name, vehicle_profile.to_dict()):
                            st.success(f"Vehicle profile '{vehicle_profile_name}' saved successfully!")
                            st.rerun()
                        else:
                            st.error("Error saving vehicle profile")
                    else:
                        st.error("Please enter a profile name")
            
            elif selected_vehicle_profile != "No Vehicle Profile" and selected_vehicle_profile != "Select Vehicle Profile":
                vehicle_profile_data = trip_planner.profile_manager.load_vehicle_profile(selected_vehicle_profile)
                if vehicle_profile_data:
                    vehicle_profile = VehicleProfile.from_dict(vehicle_profile_data)
                    vehicle_type = vehicle_profile.vehicle_type
                    fuel_type = vehicle_profile.fuel_type
                    mileage = vehicle_profile.mileage
                    tank_size = vehicle_profile.tank_size
                else:
                    st.error("Error loading vehicle profile")
        else:
            # Default values for guest users
            st.subheader("Trip Settings")
            
            # Vehicle Settings
            st.markdown("### Vehicle Settings")
            vehicle_type = st.selectbox("Vehicle Type", ["Car", "Bike"])
            fuel_type = st.selectbox("Fuel Type", ["Petrol", "Diesel"])
            mileage = st.number_input("Mileage (km/l)", min_value=1.0, value=20.0)
            tank_size = st.number_input("Tank Size (liters)", min_value=1.0, value=40.0)
            
            # Driver Preferences
            st.markdown("### Driver Preferences")
            st.markdown("Set your preferred driving hours and meal times")
            
            # Driving hours
            col1, col2 = st.columns(2)
            with col1:
                driving_hours_start = st.time_input("Preferred Driving Start Time", datetime.strptime("06:00", "%H:%M").time())
            with col2:
                driving_hours_end = st.time_input("Preferred Driving End Time", datetime.strptime("19:00", "%H:%M").time())
            
            # Meal preferences
            st.markdown("#### Meal Preferences")
            col1, col2, col3 = st.columns(3)
            with col1:
                breakfast_time = st.time_input("Breakfast Time", datetime.strptime("08:00", "%H:%M").time())
            with col2:
                lunch_time = st.time_input("Lunch Time", datetime.strptime("13:00", "%H:%M").time())
            with col3:
                dinner_time = st.time_input("Dinner Time", datetime.strptime("20:00", "%H:%M").time())
            
            # Note about guest settings
            st.info("""
            ℹ️ **Note for Guest Users:**
            - These settings will be used for your current trip only
            - Settings will not be saved after you log out
            - Consider creating an account to save your preferences for future trips
            """)
        
        # Trip details
        st.subheader("Trip Details")
        start_point = st.text_input("Starting Point", placeholder="Enter starting location")
        end_point = st.text_input("Destination", placeholder="Enter destination")
        
        # Departure date and time in columns
        col1, col2 = st.columns(2)
        with col1:
            # Set minimum date to today
            min_date = datetime.now().date()
            # Set default date to tomorrow
            default_date = min_date + timedelta(days=1)
            departure_date = st.date_input(
                "Departure Date",
                value=default_date,
                min_value=min_date,
                key="departure_date"
            )
        with col2:
            # Get current time
            current_time = datetime.now().time()
            # Set default time to 8:00 AM or current time if it's past 8 AM
            default_time = current_time if current_time.hour >= 8 else datetime.strptime("08:00", "%H:%M").time()
            departure_time = st.time_input(
                "Departure Time",
                value=default_time,
                key="departure_time"
            )
            
            # Validate time if date is today
            if departure_date == min_date and departure_time < current_time:
                st.warning("Please select a future time for today's departure")
                st.stop()
        
        # Combine date and time into a datetime object
        departure_datetime = datetime.combine(departure_date, departure_time)

    # Main content area
    if 'start_point' in locals() and 'end_point' in locals() and start_point and end_point:
        try:
            # 1. Get directions and extract route info

            # Get directions
            directions_result = maps_service.get_directions(
                start_point,
                end_point,
                mode="driving",  # Use driving mode for both cars and bikes
                departure_time=departure_datetime
            )
            if not directions_result:
                st.error("Could not get directions for the route.")
                st.stop()

            route = directions_result[0]
            leg = route['legs'][0]
            distance_km = leg['distance']['value'] / 1000

            # Convert route points to DataFrame for map display
            route_points = []
            for step in leg['steps']:
                route_points.append({'lat': step['start_location']['lat'], 'lon': step['start_location']['lng']})
                route_points.append({'lat': step['end_location']['lat'], 'lon': step['end_location']['lng']})

            # 2. Now calculate schedule, fuel_cost, toll_cost, etc.
            schedule = schedule_planner.plan_schedule(
                start_point, end_point,
                departure_datetime,
                driving_hours_start, driving_hours_end,
                breakfast_time, lunch_time, dinner_time,
                vehicle_type, mileage, tank_size
            )

            if not schedule or 'fuel_stops' not in schedule:
                st.error("Could not plan schedule or retrieve fuel stops from schedule.")
                st.stop()

            fuel_cost = fuel_service.calculate_fuel_cost(
                distance_km=distance_km,
                vehicle_type=vehicle_type,
                fuel_type=fuel_type,
                mileage=mileage,
                route_path=route_points,
                actual_fuel_stops_from_schedule=schedule['fuel_stops']
            )

            if not fuel_cost:
                st.error("Unable to fetch real-time fuel prices. Please try again later.")
                st.stop()

            toll_cost = toll_service.calculate_toll_cost(start_point, end_point, vehicle_type)

            # After all calculations, display the map at the top
            # Prepare route path for PathLayer
            route_path = [[pt['lon'], pt['lat']] for pt in route_points]

            # Prepare markers for start, end, and stops
            marker_data = []
            def get_marker_color(marker_type):
                if marker_type == "end":
                    return [255, 0, 0]
                elif marker_type == "start":
                    return [0, 255, 0]
                elif marker_type == "fuel":
                    return [0, 0, 255]
                elif marker_type == "meal":
                    return [255, 165, 0]
                elif marker_type == "rest":
                    return [128, 0, 128]
                else:
                    return [0, 0, 0]
            # Start marker
            marker_data.append({"lon": route_points[0]['lon'], "lat": route_points[0]['lat'], "type": "start", "color": get_marker_color("start")})
            # End marker
            marker_data.append({"lon": route_points[-1]['lon'], "lat": route_points[-1]['lat'], "type": "end", "color": get_marker_color("end")})
            # Stops
            if schedule.get('fuel_stops'):
                for stop in schedule['fuel_stops']:
                    if 'location' in stop:
                        loc = stop['location']
                        if isinstance(loc, dict):
                            marker_data.append({"lon": loc['lng'], "lat": loc['lat'], "type": "fuel", "color": get_marker_color("fuel")})
                        elif isinstance(loc, (list, tuple)) and len(loc) == 2:
                            marker_data.append({"lon": loc[1], "lat": loc[0], "type": "fuel", "color": get_marker_color("fuel")})
            if schedule.get('meal_stops'):
                for stop in schedule['meal_stops']:
                    if 'location' in stop:
                        loc = stop['location']
                        if isinstance(loc, dict):
                            marker_data.append({"lon": loc['lng'], "lat": loc['lat'], "type": "meal", "color": get_marker_color("meal")})
                        elif isinstance(loc, (list, tuple)) and len(loc) == 2:
                            marker_data.append({"lon": loc[1], "lat": loc[0], "type": "meal", "color": get_marker_color("meal")})
            if schedule.get('rest_stops'):
                for stop in schedule['rest_stops']:
                    if 'location' in stop:
                        loc = stop['location']
                        if isinstance(loc, dict):
                            marker_data.append({"lon": loc['lng'], "lat": loc['lat'], "type": "rest", "color": get_marker_color("rest")})
                        elif isinstance(loc, (list, tuple)) and len(loc) == 2:
                            marker_data.append({"lon": loc[1], "lat": loc[0], "type": "rest", "color": get_marker_color("rest")})

            # Create PathLayer for the route
            path_layer = pdk.Layer(
                "PathLayer",
                data=[{"path": route_path}],
                get_path="path",
                get_color=[0, 0, 255],
                width_scale=5,
                width_min_pixels=3,
            )

            # Create ScatterplotLayer for markers
            marker_layer = pdk.Layer(
                "ScatterplotLayer",
                data=marker_data,
                get_position='[lon, lat]',
                get_color='color',
                get_radius=80,
                pickable=True,
            )

            # Set the initial view state
            view_state = pdk.ViewState(
                latitude=route_points[0]['lat'],
                longitude=route_points[0]['lon'],
                zoom=6,
                pitch=0,
            )

            # Display the map at the top
            st.pydeck_chart(pdk.Deck(
                layers=[path_layer, marker_layer],
                initial_view_state=view_state,
                map_style="mapbox://styles/mapbox/dark-v10"
            ))

            # Display basic route information
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Distance", f"{leg['distance']['text']}")
            with col2:
                st.metric("Duration", f"{leg['duration']['text']}")
            
            # Calculate and display costs
            try:
                with col3:
                    total_cost = fuel_cost['fuel_cost'] + (toll_cost['total_toll'] if toll_cost else 0)
                    st.metric("Total Cost", f"₹{total_cost:.2f}")
            except Exception as e:
                st.error(f"Error calculating costs: {str(e)}")
                st.stop()
            
            # Display schedule
            st.subheader("Trip Schedule")
            
            # Create tabs for different types of stops
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Fuel Stops", "Meal Stops", "Rest Stops", "Tolls", "Sightseeing"])
            
            with tab1:
                st.write("Fuel Stops")
                if schedule.get('fuel_stops'):
                    for stop in schedule['fuel_stops']:
                        with st.container():
                            # Display station name
                            st.markdown(f"**{stop.get('name', 'Fuel Stop')}**")
                            
                            if stop.get('is_destination_stop'):
                                st.markdown("**This is your destination - tank will be filled upon arrival.**")
                            
                            # Always display address if available
                            if 'address' in stop:
                                st.markdown(f"**Address:** {stop['address']}")

                            # Display distance
                            st.markdown(f"**Distance from start:** {stop['distance']/1000:.1f} km")
                            # 'distance_from_last' is now correctly calculated in schedule.py for all stops including destination
                            if 'distance_from_last' in stop and stop['distance_from_last'] > 0 : 
                                st.markdown(f"**Distance from last stop:** {stop['distance_from_last']/1000:.1f} km")
                            elif stop.get('is_destination_stop') and stop['distance_from_last'] == stop['distance']:
                                 st.markdown(f"**Distance from last stop:** {stop['distance_from_last']/1000:.1f} km (from start - no prior stops)")

                            # Display fuel price
                            if 'price_per_liter' in stop and 'fuel_prices' in stop and 'source' in stop['fuel_prices']:
                                st.markdown(f"**Fuel Price:** ₹{stop['price_per_liter']:.2f} per liter ({stop['fuel_prices']['source']})")
                            if 'fuel_prices' in stop and 'last_updated' in stop['fuel_prices']:
                                st.markdown(f"**Last Updated:** {stop['fuel_prices']['last_updated']}")

                            # Display additional information for all stops
                            if 'rating' in stop and stop['rating'] > 0:
                                stars = '⭐' * int(stop['rating'])
                                st.markdown(f"**Rating:** {stars} ({stop['rating']:.1f})")
                            if 'is_open' in stop:
                                status = '🟢 Open' if stop['is_open'] else '🔴 Closed'
                                st.markdown(f"**Status:** {status}")
                            if 'maps_url' in stop:
                                st.markdown(f"[📍 View on Google Maps]({stop['maps_url']})")
                            
                            st.markdown("---")
                else:
                    st.info("No fuel stops planned in the schedule.")
            
            with tab2:
                st.write("Meal Stops")
                # Group meal stops by day
                meal_stops_by_day = {}
                for stop in schedule['meal_stops']:
                    day = stop.get('day', 1)  # Default to day 1 if not specified
                    if day not in meal_stops_by_day:
                        meal_stops_by_day[day] = []
                    meal_stops_by_day[day].append(stop)
                
                # Display meal stops by day
                for day in sorted(meal_stops_by_day.keys()):
                    st.markdown(f"### Day {day}")
                    for stop in meal_stops_by_day[day]:
                        with st.container():
                            st.markdown(f"### {stop['meal_type']} Stop")
                            if 'city' in stop and stop['city']:
                                st.markdown(f"**Location:** {stop['city']}")
                            st.markdown(f"**Time:** {stop['time'].strftime('%H:%M')}")
                            st.markdown(f"**Distance from start:** {stop['distance']/1000:.1f} km")
                            if 'distance_from_last' in stop:
                                st.markdown(f"**Distance from last stop:** {stop['distance_from_last']/1000:.1f} km")
                            
                            if 'restaurant_options' in stop and stop['restaurant_options']:
                                st.markdown("### Recommended Restaurants")
                                for i, restaurant in enumerate(stop['restaurant_options'], 1):
                                    with st.expander(f"{i}. {restaurant['name']}"):
                                        st.markdown(f"**Address:** {restaurant['address']}")
                                        if restaurant['rating'] > 0:
                                            stars = '⭐' * int(restaurant['rating'])
                                            st.markdown(f"**Rating:** {stars} ({restaurant['rating']:.1f})")
                                        if 'is_open' in restaurant:
                                            status = '🟢 Open' if restaurant['is_open'] else '🔴 Closed'
                                            st.markdown(f"**Status:** {status}")
                                        if 'price_level' in restaurant and restaurant['price_level'] > 0:
                                            st.markdown(f"**Price Level:** {'₹' * restaurant['price_level']}")
                                        if 'cuisine' in restaurant and restaurant['cuisine']:
                                            st.markdown(f"**Cuisine:** {restaurant['cuisine']}")
                                        if restaurant['maps_url']:
                                            st.markdown(f"[📍 View on Google Maps]({restaurant['maps_url']})")
                            else:
                                st.info("No restaurant recommendations available for this stop.")
                            
                            st.markdown("---")
            
            with tab3:
                st.write("Overnight Rest Stops")
                for idx, stop in enumerate(schedule['rest_stops']):
                    is_last = (idx == len(schedule['rest_stops']) - 1) and stop.get('is_destination', False)
                    with st.container():
                        if is_last:
                            st.markdown(f"**Destination Stop**")
                            st.success("You have reached your destination.")
                        else:
                            st.markdown(f"**Overnight Stay**")
                            if 'city' in stop and stop['city']:
                                st.markdown(f"### 🌆 {stop['city']}")
                            else:
                                st.markdown("### 🌆 Not Available")
                        st.markdown(f"**Arrival Time:** {stop['time'].strftime('%H:%M')}")
                        if not is_last and 'next_day_start' in stop:
                            st.markdown(f"**Resume Journey:** {stop['next_day_start'].strftime('%H:%M')} next day")
                        if not is_last and 'rest_duration' in stop:
                            hours = stop['rest_duration'].total_seconds() / 3600
                            st.markdown(f"**Rest Duration:** {hours:.1f} hours")
                        st.markdown(f"**Distance from start:** {stop['distance']/1000:.1f} km")
                        if 'distance_from_last' in stop:
                            st.markdown(f"**Distance from last stop:** {stop['distance_from_last']/1000:.1f} km")
                            
                            # Display hotel options if available
                            if 'hotel_options' in stop and stop['hotel_options']:
                                st.markdown("**Recommended Hotels:**")
                                for hotel in stop['hotel_options']:
                                    with st.expander(f"{hotel['name']} (Rating: {hotel['rating']:.1f})"):
                                        st.markdown(f"**Address:** {hotel['address']}")
                                        if hotel['is_open']:
                                            st.markdown("**Status:** 🟢 Open")
                                        else:
                                            st.markdown("**Status:** 🔴 Closed")
                                        if hotel['phone'] != 'Not available':
                                            st.markdown(f"**Phone:** {hotel['phone']}")
                                        if hotel['website'] != 'Not available':
                                            st.markdown(f"**Website:** {hotel['website']}")
                                        if hotel['price_level'] > 0:
                                            st.markdown(f"**Price Level:** {'₹' * hotel['price_level']}")
                                        if hotel['amenities']:
                                            st.markdown("**Amenities:**")
                                            for amenity in hotel['amenities']:
                                                st.markdown(f"- {amenity}")
                                        st.markdown(f"[View on Google Maps]({hotel['maps_url']})")
                            else:
                                st.info("No hotel recommendations available for this stop.")
                            
                            st.markdown("---")
                
                # Display total time needed for the trip
                if schedule['rest_stops']:
                    last_stop = schedule['rest_stops'][-1]
                    if 'total_time_needed' in last_stop:
                        total_hours = last_stop['total_time_needed'].total_seconds() / 3600
                        st.markdown(f"**Total Trip Duration (including rest stops):** {total_hours:.1f} hours")
            
            with tab4:
                st.write("Tolls Along the Road")
                tolls = toll_cost.get('toll_booth_details', [])
                if tolls:
                    for i, toll in enumerate(tolls, 1):
                        with st.container():
                            st.markdown(f"**Toll #{i}**")
                            if 'name' in toll:
                                toll_name = toll.get('name', 'Unknown Toll')
                                import re
                                clean_name = re.sub(r'<.*?>', ' ', toll_name)
                                clean_name = re.sub(r'\s+', ' ', clean_name).strip()
                                st.markdown(f"**Name:** {clean_name}")
                            if 'city' in toll and toll['city']:
                                st.markdown(f"**City:** {toll['city']}")
                            
                            # Display toll prices
                            prices = toll.get('prices', {})
                            st.markdown("**Toll Prices:**")
                            if prices.get('cash', 0) > 0:
                                st.markdown(f"- Cash: ₹{prices['cash']:.2f}")
                            if prices.get('tag', 0) > 0:
                                st.markdown(f"- FASTag: ₹{prices['tag']:.2f}")
                            if prices.get('return', 0) > 0:
                                st.markdown(f"- Return Pass: ₹{prices['return']:.2f}")
                            if prices.get('monthly', 0) > 0:
                                st.markdown(f"- Monthly Pass: ₹{prices['monthly']:.2f}")
                            
                            # Display payment methods
                            payment_methods = toll.get('payment_methods', [])
                            if payment_methods:
                                st.markdown("**Payment Methods:**")
                                st.markdown(", ".join(payment_methods))
                            
                            # Display Google Maps link
                            if 'maps_url' in toll and toll['maps_url']:
                                st.markdown(f"[📍 View on Google Maps]({toll['maps_url']})")
                            elif 'location' in toll:
                                loc = toll['location']
                                lat, lng = None, None
                                if isinstance(loc, dict):
                                    lat, lng = loc.get('lat'), loc.get('lng')
                                elif isinstance(loc, (list, tuple)) and len(loc) == 2:
                                    lat, lng = loc[0], loc[1]
                                if lat is not None and lng is not None:
                                    maps_url = f"https://www.google.com/maps?q={lat},{lng}"
                                    st.markdown(f"[📍 View on Google Maps]({maps_url})")
                            if 'distance' in toll:
                                st.markdown(f"**Distance from start:** {toll['distance']:.1f} km")
                            st.markdown("---")
                else:
                    st.info("No toll booths found along this route.")
            
            # Display cost breakdown
            st.subheader("Cost Breakdown")
            
            # Fuel cost section
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Fuel Cost", f"₹{fuel_cost['fuel_cost']:.2f}")
            with col2:
                # Get the last fuel stop which has the final average price
                last_stop = next((stop for stop in reversed(fuel_cost.get('refuel_stops', [])) 
                               if 'average_price_per_liter' in stop), None)
                avg_price = last_stop['average_price_per_liter'] if last_stop else fuel_cost['fuel_price']
                st.metric("Average Price per Liter", f"₹{avg_price:.2f}")
            
            st.markdown("**Fuel Details:**")
            # Calculate total fuel needed based on distance and mileage
            total_fuel_needed = distance_km / mileage # Reverted to theoretical total for the trip
            st.markdown(f"""
            - Fuel Type: {fuel_cost['fuel_type']}
            - Total Fuel Required: {total_fuel_needed:.2f} liters
            - Average Price per Liter: ₹{avg_price:.2f}
            - Source: {fuel_cost['source']}
            """)

            # Display fuel stops (Main Refuel Stops section with expanders)
            if fuel_cost and 'refuel_stops' in fuel_cost and fuel_cost['refuel_stops']:
                st.subheader("Refuel Stops")
                for stop in fuel_cost['refuel_stops']:
                    with st.expander(f"Stop at {stop.get('name', 'Unknown Fuel Stop')}"):
                        st.markdown(f"**Location:** {stop.get('state', 'Unknown State')}")
                        
                        if stop.get('is_destination_stop'):
                            st.markdown("**This is your destination - tank will be filled upon arrival.**")
                        elif 'address' in stop and stop['address'] != "Starting Point": # Starting Point address no longer relevant
                            st.markdown(f"**Address:** {stop['address']}")
                        
                        # Display segment details
                        st.markdown("**Segment Details:**")
                        # 'distance_from_last' is now correctly calculated in schedule.py
                        if 'distance_from_last' in stop and stop['distance_from_last'] > 0:
                            st.markdown(f"- Distance from last stop: {stop['distance_from_last']/1000:.1f} km")
                        elif stop.get('is_destination_stop') and stop['distance_from_last'] == stop['distance']:
                             st.markdown(f"- Distance from last stop: {stop['distance_from_last']/1000:.1f} km (from start - no prior stops)")
                        
                        if 'refill_amount' in stop:
                            st.markdown(f"- Fuel added: {stop['refill_amount']:.2f} liters")
                        if 'segment_cost' in stop:
                            st.markdown(f"- Segment cost: ₹{stop['segment_cost']:.2f}")
                        if 'price_per_liter' in stop and 'fuel_prices' in stop and 'source' in stop['fuel_prices']:
                            st.markdown(f"- Price per Liter: ₹{stop['price_per_liter']:.2f} ({stop['fuel_prices']['source']})")
                        if 'fuel_prices' in stop and 'last_updated' in stop['fuel_prices']:
                            st.markdown(f"- Last Updated: {stop['fuel_prices']['last_updated']}")
                        
                        # Display additional information if available and not destination stop
                        if not stop.get('is_destination_stop'):
                            if 'is_open' in stop:
                                st.markdown(f"**Status:** {'🟢 Open' if stop['is_open'] else '🔴 Closed'}")
                            if 'rating' in stop and stop['rating'] > 0:
                                stars = '⭐' * int(stop['rating'])
                                st.markdown(f"**Rating:** {stars} ({stop['rating']:.1f})")
                            if 'maps_url' in stop and "google.com/maps?q=" not in stop['maps_url']:
                                st.markdown(f"[📍 View on Google Maps]({stop['maps_url']})")
                        elif stop.get('is_destination_stop') and 'maps_url' in stop: # Always show map link for destination
                            st.markdown(f"[📍 View on Google Maps]({stop['maps_url']})")
            
            # Toll cost section
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total FASTag Cost", f"₹{toll_cost['total_toll']:.2f}")
            with col2:
                st.metric("Number of Toll Booths", toll_cost['toll_booths'])
            
            st.markdown("**Toll Details:**")
            st.markdown(f"- Number of Toll Booths: {toll_cost['toll_booths']}")
            if toll_cost['toll_booths'] > 0:
                avg_cost = toll_cost['total_toll']/toll_cost['toll_booths']
                st.markdown(f"- Average FASTag Cost: ₹{avg_cost:.2f} per booth")
                st.markdown(f"- Total FASTag Cost: ₹{toll_cost['total_toll']:.2f}")
                
                # Count FASTag-enabled tolls
                fastag_tolls = sum(1 for toll in toll_cost.get('toll_booth_details', []) if toll.get('is_fastag', False))
                if fastag_tolls < toll_cost['toll_booths']:
                    st.info(f"Note: {fastag_tolls} out of {toll_cost['toll_booths']} toll booths accept FASTag")
                
                # Display payment method summary
                payment_methods = set()
                for toll in toll_cost.get('toll_booth_details', []):
                    payment_methods.update(toll.get('payment_methods', []))
                if payment_methods:
                    st.markdown("**Available Payment Methods:**")
                    st.markdown(", ".join(sorted(payment_methods)))
            else:
                st.markdown("- Average Toll Cost: N/A")
            
            # Total cost summary
            st.markdown("---")
            total_cost = fuel_cost['fuel_cost'] + (toll_cost['total_toll'] if toll_cost else 0)
            st.markdown(f"""
            ### Total Trip Cost: ₹{total_cost:.2f}
            - Total Distance: {distance_km:.1f} km
            - Total Duration: {leg['duration']['text']}
            """)

            with tab5:
                st.write("Sightseeing Spots")
                spots = get_sightseeing_spots(start_point, end_point, route_points)
                
                if spots:
                    for spot in spots:
                        with st.container():
                            st.markdown(f"### {spot['name']}")
                            st.markdown(f"**Type:** {spot['type']}")
                            st.markdown(f"**Description:** {spot['description']}")
                            st.markdown(f"**Best Time to Visit:** {spot['best_time']}")
                            
                            if 'maps_url' in spot:
                                st.markdown(f"[📍 View on Google Maps]({spot['maps_url']})")
                            
                            st.markdown("---")
                else:
                    st.info("No sightseeing spots found along this route.")
        
        except Exception as e:
            st.error(f"Error calculating route: {str(e)}")
    else:
        st.info("Please enter both starting point and destination to plan your route.")

# Footer
st.markdown("---")
st.markdown("Built with ❤️ for Indian road trippers") 