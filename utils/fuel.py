import os
from dotenv import load_dotenv
import requests
from datetime import datetime
from .places import PlacesService
from .maps import MapsService
import google.generativeai as genai

load_dotenv()

class FuelService:
    def __init__(self):
        self.places_service = PlacesService()
        # Initialize Gemini API
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not self.gemini_api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables")
        else:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
            print("Gemini API initialized for fuel prices")
        
        # Fallback prices by state (as of March 2024)
        self.fallback_prices = {
            'delhi': {'petrol': 96.72, 'diesel': 89.62},
            'haryana': {'petrol': 96.20, 'diesel': 84.26},
            'punjab': {'petrol': 96.20, 'diesel': 84.26},
            'rajasthan': {'petrol': 108.48, 'diesel': 93.72},
            'uttar pradesh': {'petrol': 96.57, 'diesel': 89.76},
            'bihar': {'petrol': 107.24, 'diesel': 94.04},
            'jharkhand': {'petrol': 107.24, 'diesel': 94.04},
            'west bengal': {'petrol': 106.03, 'diesel': 92.76},
            'odisha': {'petrol': 103.29, 'diesel': 94.86},
            'chhattisgarh': {'petrol': 108.14, 'diesel': 93.28},
            'madhya pradesh': {'petrol': 108.14, 'diesel': 93.28},
            'gujarat': {'petrol': 96.72, 'diesel': 89.62},
            'maharashtra': {'petrol': 106.31, 'diesel': 94.27},
            'goa': {'petrol': 101.84, 'diesel': 87.79},
            'karnataka': {'petrol': 101.94, 'diesel': 87.89},
            'telangana': {'petrol': 109.66, 'diesel': 97.82},
            'andhra pradesh': {'petrol': 109.66, 'diesel': 97.82},
            'tamil nadu': {'petrol': 102.63, 'diesel': 94.24},
            'kerala': {'petrol': 107.97, 'diesel': 97.21},
            'assam': {'petrol': 97.22, 'diesel': 89.95},
            'arunachal pradesh': {'petrol': 97.22, 'diesel': 89.95},
            'nagaland': {'petrol': 97.22, 'diesel': 89.95},
            'manipur': {'petrol': 97.22, 'diesel': 89.95},
            'mizoram': {'petrol': 97.22, 'diesel': 89.95},
            'tripura': {'petrol': 97.22, 'diesel': 89.95},
            'meghalaya': {'petrol': 97.22, 'diesel': 89.95},
            'sikkim': {'petrol': 97.22, 'diesel': 89.95},
            'jammu and kashmir': {'petrol': 96.20, 'diesel': 84.26},
            'himachal pradesh': {'petrol': 96.20, 'diesel': 84.26},
            'uttarakhand': {'petrol': 96.20, 'diesel': 84.26},
            'chandigarh': {'petrol': 96.20, 'diesel': 84.26},
            'dadra and nagar haveli': {'petrol': 101.84, 'diesel': 87.79},
            'daman and diu': {'petrol': 101.84, 'diesel': 87.79},
            'puducherry': {'petrol': 102.63, 'diesel': 94.24},
            'andaman and nicobar islands': {'petrol': 97.22, 'diesel': 89.95},
            'lakshadweep': {'petrol': 101.84, 'diesel': 87.79}
        }
    
    def get_fuel_prices(self, city):
        """
        Get current fuel prices for a city using Gemini API
        """
        try:
            print("\n=== Starting fuel price fetch ===")
            print(f"Target city: {city}")
            
            # Create prompt for Gemini
            prompt = f"""What are the current petrol and diesel prices in {city}, India? 
            Please provide the prices in the following format:
            Petrol: ₹XX.XX
            Diesel: ₹XX.XX
            
            Only return the prices in the exact format above, nothing else."""
            
            print("Sending request to Gemini API...")
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                print("No response from Gemini API")
                return self._get_fallback_prices(city)
            
            print(f"Gemini API response: {response.text}")
            
            # Parse the response
            try:
                lines = response.text.strip().split('\n')
                petrol_price = None
                diesel_price = None
                
                for line in lines:
                    if 'Petrol:' in line:
                        petrol_price = float(line.split('₹')[1].strip())
                    elif 'Diesel:' in line:
                        diesel_price = float(line.split('₹')[1].strip())
                
                if not petrol_price or not diesel_price:
                    print("Could not parse prices from response")
                    print(f"Petrol price found: {petrol_price}")
                    print(f"Diesel price found: {diesel_price}")
                    return self._get_fallback_prices(city)
                
                print(f"Successfully parsed prices - Petrol: ₹{petrol_price}, Diesel: ₹{diesel_price}")
                
                return {
                    'petrol': petrol_price,
                    'diesel': diesel_price,
                    'city': city,
                    'is_estimate': False,
                    'source': 'Gemini API',
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
            except Exception as e:
                print(f"Error parsing Gemini response: {str(e)}")
                print(f"Raw response: {response.text}")
                return self._get_fallback_prices(city)
            
        except Exception as e:
            print(f"Error fetching fuel prices: {str(e)}")
            import traceback
            print(f"Error traceback: {traceback.format_exc()}")
            return self._get_fallback_prices(city)
    
    def _get_fallback_prices(self, city, address=None):
        """
        Get fallback fuel prices based on state
        """
        try:
            state = None
            
            # First try to get state from address if provided
            if address:
                # Common state names and their variations
                state_mapping = {
                    'odisha': ['odisha', 'orissa'],
                    'andhra pradesh': ['andhra pradesh', 'andhra'],
                    'west bengal': ['west bengal', 'bengal'],
                    'karnataka': ['karnataka'],
                    'tamil nadu': ['tamil nadu', 'tamilnadu'],
                    'kerala': ['kerala'],
                    'maharashtra': ['maharashtra'],
                    'gujarat': ['gujarat'],
                    'rajasthan': ['rajasthan'],
                    'madhya pradesh': ['madhya pradesh', 'mp'],
                    'uttar pradesh': ['uttar pradesh', 'up'],
                    'bihar': ['bihar'],
                    'jharkhand': ['jharkhand'],
                    'chhattisgarh': ['chhattisgarh'],
                    'telangana': ['telangana'],
                    'haryana': ['haryana'],
                    'punjab': ['punjab'],
                    'himachal pradesh': ['himachal pradesh', 'hp'],
                    'uttarakhand': ['uttarakhand', 'uk'],
                    'delhi': ['delhi', 'nct'],
                    'chandigarh': ['chandigarh'],
                    'goa': ['goa'],
                    'assam': ['assam'],
                    'arunachal pradesh': ['arunachal pradesh', 'arunachal'],
                    'nagaland': ['nagaland'],
                    'manipur': ['manipur'],
                    'mizoram': ['mizoram'],
                    'tripura': ['tripura'],
                    'meghalaya': ['meghalaya'],
                    'sikkim': ['sikkim'],
                    'jammu and kashmir': ['jammu and kashmir', 'j&k'],
                    'dadra and nagar haveli': ['dadra and nagar haveli'],
                    'daman and diu': ['daman and diu'],
                    'puducherry': ['puducherry', 'pondicherry'],
                    'andaman and nicobar islands': ['andaman and nicobar', 'andaman'],
                    'lakshadweep': ['lakshadweep']
                }
                
                address_lower = address.lower()
                for state_name, variations in state_mapping.items():
                    if any(var in address_lower for var in variations):
                        state = state_name
                        break
            
            # If state not found in address, try reverse geocoding
            if not state:
                maps_service = MapsService()
                location = maps_service.get_reverse_geocode(0, 0)  # This will be updated with actual coordinates
                
                if location and len(location) > 0:
                    for component in location[0]['address_components']:
                        if 'administrative_area_level_1' in component['types']:
                            state = component['long_name'].lower()
                            break
            
            if not state:
                print(f"Could not determine state for {city}, using Delhi prices")
                return {
                    'petrol': self.fallback_prices['delhi']['petrol'],
                    'diesel': self.fallback_prices['delhi']['diesel'],
                    'city': city,
                    'is_estimate': True,
                    'source': 'Fallback Prices (State: Delhi)',
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            # Try to find state in fallback prices
            state_prices = None
            for state_name, prices in self.fallback_prices.items():
                if state in state_name or state_name in state:
                    state_prices = prices
                    break
            
            if not state_prices:
                print(f"No fallback prices found for state {state}, using Delhi prices")
                state_prices = self.fallback_prices['delhi']
                state = 'delhi'
            
            return {
                'petrol': state_prices['petrol'],
                'diesel': state_prices['diesel'],
                'city': city,
                'is_estimate': True,
                'source': f'Fallback Prices (State: {state.title()})',
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"Error getting fallback prices: {str(e)}")
            return {
                'petrol': self.fallback_prices['delhi']['petrol'],
                'diesel': self.fallback_prices['delhi']['diesel'],
                'city': city,
                'is_estimate': True,
                'source': 'Fallback Prices (State: Delhi)',
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def calculate_fuel_cost(self, distance_km, vehicle_type, fuel_type, mileage, tank_size=None, route_path=None, actual_fuel_stops_from_schedule=None):
        """
        Calculate fuel cost for a trip based on a pre-calculated schedule of fuel stops.
        """
        try:
            # This is for the summary; individual stops retain their own source/state.
            overall_source = 'Mixed sources'
            # Default overall_state_or_city before checking the first stop
            overall_state_or_city = 'Starting location not specified' 
            city_for_fallback_logic = "Unknown City" # Initialize for the if not actual_fuel_stops_from_schedule block

            if not actual_fuel_stops_from_schedule:
                print("Warning: calculate_fuel_cost called without actual_fuel_stops_from_schedule. Cannot calculate detailed costs.")
                # Fallback to a simple calculation if no detailed stops are provided
                maps_service = MapsService()
                # city_for_fallback_logic remains "Unknown City" unless updated by reverse geocode
                if route_path and len(route_path) > 0:
                    start_location = route_path[0]
                    if isinstance(start_location, dict):
                        lat, lng = start_location.get('lat'), start_location.get('lon')
                    elif isinstance(start_location, (list, tuple)) and len(start_location) >= 2:
                        lat, lng = start_location[0], start_location[1]
                    else: lat, lng = None, None
                    if lat is not None and lng is not None:
                        current_location_data = maps_service.get_reverse_geocode(lat, lng)
                        if current_location_data and len(current_location_data) > 0:
                            for component in current_location_data[0]['address_components']:
                                if 'locality' in component['types']:
                                    city_for_fallback_logic = component['long_name']
                                    break
                                elif 'administrative_area_level_1' in component['types']:
                                    city_for_fallback_logic = component['long_name']
                                    break
                initial_fuel_prices = self.get_fuel_prices(city_for_fallback_logic)
                if not initial_fuel_prices: return None
                fuel_required = distance_km / mileage
                price_key = 'petrol' if fuel_type.lower() == 'petrol' else 'diesel'
                cost = fuel_required * initial_fuel_prices.get(price_key, 0)
                return {
                    'fuel_cost': cost,
                    'fuel_required': fuel_required,
                    'fuel_price': initial_fuel_prices.get(price_key, 0),
                    'fuel_type': fuel_type,
                    'is_estimate': True, # Mark as estimate as no stops were processed
                    'source': initial_fuel_prices.get('source', 'Fallback'),
                    'state': city_for_fallback_logic,
                    'refuel_stops': []
                }

            # This is the main logic path when actual_fuel_stops_from_schedule is provided
            total_cost_from_stops = 0
            total_fuel_from_stops = 0
            processed_refuel_stops = []

            for stop in actual_fuel_stops_from_schedule:
                total_cost_from_stops += stop.get('segment_cost', 0)
                total_fuel_from_stops += stop.get('refill_amount', stop.get('segment_fuel', 0))
                processed_refuel_stops.append(stop)
            
            avg_price_per_liter = total_cost_from_stops / total_fuel_from_stops if total_fuel_from_stops > 0 else 0
            
            if processed_refuel_stops:
                first_stop = processed_refuel_stops[0]
                if first_stop.get('fuel_prices'):
                    overall_source = first_stop['fuel_prices'].get('source', 'Gemini API')
                # 'state' in the stop dict should hold the city/state of that stop
                overall_state_or_city = first_stop.get('state', 'Unknown Starting State') 

            print(f"FuelService: Total cost from stops: {total_cost_from_stops}, Total fuel: {total_fuel_from_stops}")

            return {
                'fuel_cost': total_cost_from_stops,
                'fuel_required': total_fuel_from_stops, # This is total fuel *added*
                'fuel_price': avg_price_per_liter, # This is the effective average price
                'fuel_type': fuel_type, # Preserve original fuel_type for display
                'is_estimate': False, # Based on detailed stops
                'source': overall_source,
                'state': overall_state_or_city, # Or starting city/state for overall summary
                'refuel_stops': processed_refuel_stops
            }

        except Exception as e:
            print(f"Error in FuelService.calculate_fuel_cost: {str(e)}")
            import traceback
            print(f"Error traceback: {traceback.format_exc()}")
            return None 