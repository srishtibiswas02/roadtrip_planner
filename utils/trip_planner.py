import streamlit as st
from datetime import datetime
from .maps import MapsService
from .places import PlacesService
from .tolls import TollService
from .schedule import SchedulePlanner
from .fuel import FuelService
from .profiles import ProfileManager
from .auth import AuthManager
from .llm import LLMService

class TripPlanner:
    def __init__(self):
        self.maps_service = MapsService()
        self.places_service = PlacesService()
        self.toll_service = TollService()
        self.schedule_planner = SchedulePlanner()
        self.fuel_service = FuelService()
        self.profile_manager = ProfileManager()
        self.auth_manager = AuthManager()
        self.llm_service = LLMService()

    def get_sightseeing_spots(self, start_point, end_point, route_points):
        """Get sightseeing spots along the route using LLMService"""
        try:
            # Get spots from LLM service
            spots = self.llm_service.get_sightseeing_spots(start_point, end_point)
            
            # Get additional details for each spot
            for spot in spots:
                try:
                    details = self.llm_service.get_spot_details(
                        spot['name'],
                        route_points[0],  # Use first point of route as reference
                        self.places_service,
                        self.maps_service
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

    def login(self, username: str, password: str) -> bool:
        return self.auth_manager.verify_user(username, password)

    def register(self, username: str, password: str, email: str) -> bool:
        return self.auth_manager.register_user(username, password, email)

    def guest_login(self):
        return self.auth_manager.guest_login()

    def get_marker_color(self, marker_type):
        """Get color for different types of markers"""
        colors = {
            'start': [0, 255, 0],  # Green
            'end': [255, 0, 0],    # Red
            'stop': [0, 0, 255],   # Blue
            'hotel': [255, 165, 0], # Orange
            'restaurant': [128, 0, 128], # Purple
            'sightseeing': [255, 255, 0] # Yellow
        }
        return colors.get(marker_type, [128, 128, 128])  # Default gray 