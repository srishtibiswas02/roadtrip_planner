import googlemaps
from datetime import datetime
import os
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

class MapsService:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.api_key:
            raise ValueError("Google Maps API key not found in environment variables")
        self.client = googlemaps.Client(key=self.api_key)
    
    def get_geocode(self, address):
        """
        Get geocoding information for an address
        """
        try:
            return self.client.geocode(address)
        except Exception as e:
            print(f"Error geocoding address: {str(e)}")
            return None
    
    def get_directions(self, start_point, end_point, mode="driving", departure_time=None, alternatives=False):
        """
        Get directions between two points with toll information
        """
        try:
            print(f"\nAttempting to get directions:")
            print(f"Start: {start_point}")
            print(f"End: {end_point}")
            print(f"Mode: {mode}")
            print(f"Departure time: {departure_time}")
            
            # Prepare directions request parameters
            params = {
                'origin': start_point,
                'destination': end_point,
                'mode': mode,
                'alternatives': alternatives,
                'language': 'en',
                'region': 'in'  # Set region to India for better toll information
            }
            
            # Add departure time if provided
            if departure_time:
                params['departure_time'] = departure_time
            
            print(f"Request parameters: {params}")
            
            # Get directions
            directions = self.client.directions(**params)
            
            if not directions:
                print("No directions returned from Google Maps API")
                return None
            
            print(f"Successfully got directions with {len(directions)} routes")
            return directions
            
        except Exception as e:
            print(f"Error getting directions: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            if hasattr(e, 'response'):
                print(f"API Response: {e.response}")
            return None
    
    def get_place_details(self, place_id):
        """
        Get detailed information about a place
        """
        try:
            return self.client.place(place_id)
        except Exception as e:
            print(f"Error getting place details: {str(e)}")
            return None
    
    def search_places(self, query, location=None, radius=None):
        """
        Search for places near a location
        """
        try:
            params = {
                'query': query
            }
            
            if location and radius:
                params['location'] = location
                params['radius'] = radius
            
            return self.client.places(**params)
        except Exception as e:
            print(f"Error searching places: {str(e)}")
            return None
    
    def search_nearby_places(self, location, radius, place_type):
        """
        Search for places near a location
        """
        return self.client.places_nearby(
            location=location,
            radius=radius,
            type=place_type
        )
    
    def get_reverse_geocode(self, lat, lng):
        """
        Convert coordinates to address
        """
        return self.client.reverse_geocode((lat, lng))
    
    def get_distance_matrix(self, origins, destinations, mode="driving"):
        """
        Calculate distance and duration between multiple origins and destinations
        """
        return self.client.distance_matrix(
            origins,
            destinations,
            mode=mode
        )
    
    def get_static_map_url(self, route_points, stops=None, size="800x500"):
        """
        Generate a Google Static Maps API URL with a route polyline and markers for start, end, and stops.
        Args:
            route_points: List of dicts with 'lat' and 'lon' for the route polyline
            stops: List of dicts with 'lat', 'lon', and optional 'label' for stops (fuel, meal, rest)
            size: Image size (default 800x500)
        Returns:
            URL string for the static map
        """
        base_url = "https://maps.googleapis.com/maps/api/staticmap?"
        params = {
            "size": size,
            "maptype": "roadmap",
            "key": self.api_key
        }
        # Polyline path (as lat,lng pairs)
        if route_points:
            path = "color:0x0000ff|weight:5"
            for pt in route_points:
                path += f"|{pt['lat']},{pt['lon']}"
            params["path"] = path
        # Markers
        markers = []
        if route_points:
            # Start marker (green)
            start = route_points[0]
            markers.append(f"color:green|label:S|{start['lat']},{start['lon']}")
            # End marker (red)
            end = route_points[-1]
            markers.append(f"color:red|label:E|{end['lat']},{end['lon']}")
        if stops:
            for i, stop in enumerate(stops):
                label = stop.get('label', chr(65 + (i % 26)))  # A, B, C, ...
                markers.append(f"color:blue|label:{label}|{stop['lat']},{stop['lon']}")
        # Add all markers
        params['markers'] = markers
        # Build URL
        url = base_url + urllib.parse.urlencode(params, doseq=True)
        return url 