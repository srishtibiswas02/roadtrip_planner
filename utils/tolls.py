import requests

from datetime import datetime
import os
from dotenv import load_dotenv
import googlemaps
import polyline
import math
import hashlib
import base64

load_dotenv()



class TollService:
    def __init__(self):
        self.api_key = os.getenv('TOLLGURU_API_KEY')
        if not self.api_key:
            print("Warning: TOLLGURU_API_KEY not found in environment variables")
        else:
            # Mask the API key for security when logging
            masked_key = self.api_key[:4] + '*' * (len(self.api_key) - 8) + self.api_key[-4:]
            print(f"TollGuru API key loaded: {masked_key}")
        
        # Initialize Google Maps client for fallback
        self.gmaps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.gmaps_api_key:
            print("Warning: GOOGLE_MAPS_API_KEY not found in environment variables")
        else:
            self.client = googlemaps.Client(key=self.gmaps_api_key)
            print("Google Maps client initialized for toll calculations")
    
    def _format_api_key(self, api_key):
        """Format API key according to TollGuru requirements"""
        # Create the key=value pair
        key_value = f"key={api_key}"
        # Hash with SHA-256
        hashed = hashlib.sha256(key_value.encode()).digest()
        # Encode with Base64
        encoded = base64.b64encode(hashed).decode()
        # Add the algorithm name
        return f"SHA256 {encoded}"

    def calculate_toll_cost(self, start_point, end_point, vehicle_type):
        """
        Calculate toll costs for a route using TollGuru API
        """
        if not self.api_key:
            print("TollGuru API key not found, cannot fetch toll data")
            return {
                'total_toll': 0,
                'distance_km': 0,
                'toll_booths': 0,
                'vehicle_type': vehicle_type,
                'is_estimate': True,
                'toll_booth_details': []
            }
        
        # Map vehicle_type to TollGuru's India vehicle types
        vehicle_type_map = {
            'Car': '2AxlesAuto',
            'Bike': '2AxlesMotorcycle',
            'Taxi': '2AxlesTaxi',
            'LCV': '2AxlesLCV',
            'Truck': '2AxlesTruck',
            'Bus': '2AxlesBus',
        }
        tg_vehicle_type = vehicle_type_map.get(vehicle_type, '2AxlesAuto')
        
        try:
            tolls, total_cost = self.get_tollguru_tolls(start_point, end_point, tg_vehicle_type)
            return {
                'total_toll': total_cost,
                'distance_km': None,
                'toll_booths': len(tolls),
                'vehicle_type': vehicle_type,
                'is_estimate': False,
                'toll_booth_details': tolls
            }
        except Exception as e:
            print(f"Error calculating toll cost: {str(e)}")
            return {
                'total_toll': 0,
                'distance_km': 0,
                'toll_booths': 0,
                'vehicle_type': vehicle_type,
                'is_estimate': True,
                'toll_booth_details': []
            }

    def get_tollguru_tolls(self, source, destination, vehicle_type="2AxlesAuto"): 
        url = "https://apis.tollguru.com/toll/v2/origin-destination-waypoints"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        payload = {
            "from": {"address": source},
            "to": {"address": destination},
            "vehicleType": vehicle_type,
            "serviceProvider": "tollguru",
            "getPathPolygon": True,
            "getVehicleStops": True
        }
        try:
            print("\n=== TollGuru API Request ===")
            print(f"URL: {url}")
            print(f"Source: {source}")
            print(f"Destination: {destination}")
            print(f"Vehicle Type: {vehicle_type}")
            print(f"Headers: {headers}")
            print(f"Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            print("\n=== TollGuru API Response ===")
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 403:
                print("Authentication failed. Please check your TollGuru API key.")
                print("Response body:", response.text)
                return [], 0
                
            response.raise_for_status()
            data = response.json()
            print(f"Response Data: {data}")
            
            if not data.get('routes'):
                print('No routes found in TollGuru API response')
                return [], 0
                
            route = data['routes'][0]  # Get the first route
            tolls = []
            total_cost = 0
            
            print("\n=== Processing Toll Data ===")
            for toll in route.get('tolls', []):
                name = toll.get('name', 'Toll Plaza')
                city = toll.get('city', None)
                
                # Extract toll prices
                prices = {
                    'cash': float(toll.get('cashCost', 0)),
                    'tag': float(toll.get('tagCost', 0)),
                    'return': float(toll.get('returnCost', 0)),
                    'monthly': float(toll.get('monthlyCost', 0))
                }
                
                # Always use FASTag cost if available, otherwise use cash cost
                cost = prices['tag'] if prices['tag'] > 0 else prices['cash']
                total_cost += cost
                
                location = toll.get('location', {})
                lat = location.get('lat')
                lng = location.get('lng')
                # Fix Google Maps URL format
                maps_url = f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else None
                
                # Get payment methods
                payment_methods = []
                if prices['cash'] > 0:
                    payment_methods.append('Cash')
                if prices['tag'] > 0:
                    payment_methods.append('FASTag')
                if prices['return'] > 0:
                    payment_methods.append('Return Pass')
                if prices['monthly'] > 0:
                    payment_methods.append('Monthly Pass')
                
                toll_data = {
                    'name': name,
                    'city': city,
                    'cost': cost,
                    'prices': prices,
                    'location': {'lat': lat, 'lng': lng} if lat and lng else None,
                    'maps_url': maps_url,
                    'payment_methods': payment_methods,
                    'is_return': prices['return'] > 0,
                    'is_monthly': prices['monthly'] > 0,
                    'is_fastag': prices['tag'] > 0
                }
                tolls.append(toll_data)
                print(f"Processed toll: {toll_data}")
            
            print(f"\nTotal tolls found: {len(tolls)}")
            print(f"Total FASTag cost: {total_cost}")
            return tolls, total_cost
            
        except requests.exceptions.RequestException as e:
            print(f"\n=== Error Details ===")
            print(f"Network error calling TollGuru API: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response Status: {e.response.status_code}")
                print(f"Response Headers: {dict(e.response.headers)}")
                print(f"Response Body: {e.response.text}")
            return [], 0
        except ValueError as e:
            print(f"\n=== Error Details ===")
            print(f"Invalid response from TollGuru API: {str(e)}")
            return [], 0
        except Exception as e:
            print(f"\n=== Error Details ===")
            print(f"Unexpected error calling TollGuru API: {str(e)}")
            return [], 0
    
    def calculate_toll_cost_google(self, start_point, end_point, vehicle_type):
        """
        Calculate toll costs for a route using Google Routes API
        """
        try:
            # Check if API key is available
            if not self.api_key:
                print("Google Maps API key not found, cannot fetch toll data")
                return {
                    'total_toll': 0,
                    'distance_km': 0,
                    'toll_booths': 0,
                    'vehicle_type': vehicle_type,
                    'is_estimate': True,
                    'toll_booth_details': []
                }
            
            # Get route information from Google Maps API
            from .maps import MapsService
            maps_service = MapsService()
            
            # Get directions with toll information
            directions = maps_service.get_directions(
                start_point,
                end_point,
                mode="driving",  # Use driving mode for both cars and bikes
                alternatives=False
            )
            
            if not directions:
                return {
                    'total_toll': 0,
                    'distance_km': 0,
                    'toll_booths': 0,
                    'vehicle_type': vehicle_type,
                    'is_estimate': True,
                    'toll_booth_details': []
                }
            
            route = directions[0]
            leg = route['legs'][0]
            total_distance = leg['distance']['value'] / 1000  # Convert to km
            
            # Extract tolls along the route from the steps
            toll_booths = self.extract_tolls_from_route_steps(leg, vehicle_type)
            
            # Calculate total toll cost
            total_toll = sum(booth.get('cost', 0) for booth in toll_booths)
            
            return {
                'total_toll': total_toll,
                'distance_km': total_distance,
                'toll_booths': len(toll_booths),
                'vehicle_type': vehicle_type,
                'is_estimate': True,  # We're still estimating toll costs
                'toll_booth_details': toll_booths
            }
            
        except Exception as e:
            print(f"Error calculating toll with Google API: {str(e)}")
            return {
                'total_toll': 0,
                'distance_km': 0,
                'toll_booths': 0,
                'vehicle_type': vehicle_type,
                'is_estimate': True,
                'toll_booth_details': []
            }
    
    def extract_tolls_from_route_steps(self, leg, vehicle_type):
        toll_booths = []
        try:
            for step in leg.get('steps', []):
                html = step.get('html_instructions', '').lower()
                # Look for toll indicators in the step
                if any(word in html for word in ['toll', 'plaza', 'fastag', 'expressway']):
                    step_distance = step['distance']['value'] / 1000  # km
                    toll_cost = self._calculate_toll_cost(step_distance, vehicle_type)
                    name = self._clean_html(step.get('html_instructions', 'Toll Booth'))
                    lat = step['start_location']['lat']
                    lng = step['start_location']['lng']
                    city = self.get_city_name(lat, lng)
                    maps_url = f"https://www.google.com/maps?q={lat},{lng}"
                    toll_booths.append({
                        'name': name,
                        'location': {'lat': lat, 'lng': lng},
                        'cost': toll_cost,
                        'distance': step_distance,
                        'is_real': True,
                        'city': city,
                        'maps_url': maps_url
                    })
            return toll_booths
        except Exception as e:
            print(f"Error extracting tolls from route steps: {str(e)}")
            return []
    
    def get_city_name(self, lat, lng):
        try:
            if not self.api_key:
                return None
            result = self.client.reverse_geocode((lat, lng))
            if not result:
                return None
            for component in result[0]['address_components']:
                if 'locality' in component['types']:
                    return component['long_name']
                elif 'administrative_area_level_2' in component['types']:
                    return component['long_name']
                elif 'administrative_area_level_1' in component['types']:
                    return component['long_name']
            return None
        except Exception as e:
            print(f"Error getting city name: {str(e)}")
            return None
    
    def _calculate_toll_cost(self, distance_km, vehicle_type):
        """
        Calculate toll cost based on distance and vehicle type
        """
        # Toll rates per km (in INR) - more accurate rates for different road types
        toll_rates = {
            'Car': {
                'highway': 3.0,    # ₹3.0 per km for highways
                'expressway': 4.0,  # ₹4.0 per km for expressways
                'default': 2.5     # ₹2.5 per km for other roads
            },
            'Bike': 0  # Bikes are usually exempt from tolls
        }
        
        if vehicle_type == 'Bike':
            return 0
        
        # Use a weighted average of toll rates
        car_rates = toll_rates['Car']
        avg_rate = (car_rates['highway'] * 0.4 +  # 40% highways
                   car_rates['expressway'] * 0.2 +  # 20% expressways
                   car_rates['default'] * 0.4)     # 40% other roads
        
        return distance_km * avg_rate
    
    def _clean_html(self, html_text):
        """
        Remove HTML tags from text for cleaner display
        """
        import re
        # Basic HTML tag removal
        clean_text = re.sub(r'<.*?>', ' ', html_text)
        # Replace multiple spaces with a single space
        clean_text = re.sub(r'\s+', ' ', clean_text)
        return clean_text.strip()
    
    def _haversine(self, loc1, loc2):
        # Returns distance in km between two lat/lng dicts
        from math import radians, cos, sin, asin, sqrt
        lat1, lon1 = loc1['lat'], loc1['lng']
        lat2, lon2 = loc2['lat'], loc2['lng']
        # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r
    
    def _similar_name(self, name1, name2):
        # Simple similarity: ignore case, spaces, and compare startswith or endswith
        n1 = name1.lower().replace(' ', '')
        n2 = name2.lower().replace(' ', '')
        return n1.startswith(n2[:6]) or n2.startswith(n1[:6]) or n1.endswith(n2[-6:]) or n2.endswith(n1[-6:]) 