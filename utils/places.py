from .maps import MapsService
from datetime import datetime, time
import os
from dotenv import load_dotenv
import googlemaps

load_dotenv()

class PlacesService:
    def __init__(self):
        self.maps_service = MapsService()
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not found in environment variables")
        
        self.client = googlemaps.Client(key=self.api_key)
    
    def find_fuel_stations(self, location, radius=5000):
        """
        Find fuel stations near a location
        """
        return self.maps_service.search_nearby_places(
            location=location,
            radius=radius,
            place_type="gas_station"
        )
    
    def find_restaurants(self, location, radius=5000, cuisine_type=None):
        """
        Find restaurants near a location
        """
        places = self.maps_service.search_nearby_places(
            location=location,
            radius=radius,
            place_type="restaurant"
        )
        
        if cuisine_type:
            # Filter by cuisine type if specified
            places['results'] = [
                place for place in places['results']
                if cuisine_type.lower() in [t.lower() for t in place.get('types', [])]
            ]
        
        return places
    
    def find_hotels(self, location, radius=10000, min_rating=3.5):
        """
        Find hotels near a location using Places API
        """
        try:
            print(f"\n=== Finding hotels near {location} ===")
            print(f"Radius: {radius}m, Min rating: {min_rating}")
            
            # First try with 'lodging' type
            response = self.client.places_nearby(
                location=location,
                radius=radius,
                type='lodging',
                keyword='hotel'
            )
            
            print(f"Places API Response (lodging): {response}")  # Debug line
            
            if not response.get('results'):
                # If no results, try with just 'hotel' keyword
                response = self.client.places_nearby(
                    location=location,
                    radius=radius,
                    keyword='hotel'
                )
                print(f"Places API Response (keyword only): {response}")  # Debug line
            
            if response.get('results'):
                # Filter by minimum rating
                filtered_results = [
                    place for place in response['results']
                    if place.get('rating', 0) >= min_rating
                ]
                print(f"Found {len(filtered_results)} hotels with rating >= {min_rating}")
                return {'results': filtered_results}
            else:
                print("No hotels found")
                return {'results': []}
                
        except Exception as e:
            print(f"Error finding hotels: {str(e)}")
            return {'results': []}
    
    def get_place_details(self, place_id):
        """
        Get detailed information about a place using Places API
        """
        try:
            print(f"\n=== Getting details for place: {place_id} ===")
            
            response = self.client.place(
                place_id=place_id,
                fields=['name', 'formatted_address', 'rating', 'opening_hours', 'url', 
                       'geometry', 'place_id', 'price_level', 'business_status',
                       'formatted_phone_number', 'website', 'type', 'dine_in',
                       'serves_breakfast', 'serves_lunch', 'serves_dinner']
            )
            
            if response.get('result'):
                print(f"Found details for: {response['result'].get('name')}")
                return response['result']
            else:
                print("No details found")
                return None
                
        except Exception as e:
            print(f"Error getting place details: {str(e)}")
            return None
    
    def find_rest_stops(self, location, radius=5000):
        """
        Find rest stops near a location
        """
        return self.maps_service.search_nearby_places(
            location=location,
            radius=radius,
            place_type="rest_stop"
        )
    
    def find_attractions(self, location, radius=5000):
        """
        Find tourist attractions near a location
        """
        return self.maps_service.search_nearby_places(
            location=location,
            radius=radius,
            place_type="tourist_attraction"
        )
    
    def get_reverse_geocode(self, lat, lng):
        try:
            reverse_geocode_result = self.client.reverse_geocode((lat, lng))
            return reverse_geocode_result
        except Exception as e:
            print(f"Error during reverse geocoding: {e}")
            return None

    def get_nearest_state(self, lat, lng):
        """
        Determines the state for a given latitude and longitude using reverse geocoding.
        """
        try:
            reverse_geocode_result = self.client.reverse_geocode((lat, lng))
            if reverse_geocode_result:
                for component in reverse_geocode_result[0].get('address_components', []):
                    if 'administrative_area_level_1' in component.get('types', []):
                        return component.get('long_name')
            return "Unknown State" # Fallback if state not found
        except Exception as e:
            print(f"Error during get_nearest_state: {e}")
            return "Unknown State" # Fallback on error

    def get_fuel_station(self, distance_km, route_path, total_distance_km, radius=50000):
        """
        Fetch fuel station near a point on the route using Google Places API.
        Args:
            distance_km: Distance along the route (km) to find a fuel station.
            route_path: List of [lat, lng] coordinates from the route.
            total_distance_km: Total route distance in kilometers.
            radius: Search radius in meters (default: 50000m = 50km)
        Returns: Dict with name, rating, open_now, and location.
        Raises: Exception on API errors (e.g., invalid key, no results, network issues).
        """
        if not self.api_key:
            raise ValueError("Google Places API key is missing. Set GOOGLE_MAPS_API_KEY in your .env file.")

        try:
            # Estimate location at distance_km along the route
            if total_distance_km <= 0:
                raise ValueError("Total route distance must be greater than zero")
            path_index = min(int(len(route_path) * (distance_km / total_distance_km)), len(route_path) - 1)
            location = route_path[path_index]
            
            print(f"\n=== Finding fuel station near {distance_km}km (PlacesService.get_fuel_station) ===")
            print(f"   Target Coordinates: {location}")
            print(f"   Search Radius: {radius}m, Type: gas_station, Rank By: prominence")

            # Fetch nearby fuel stations
            places_result = self.client.places_nearby(
                location=(location[0], location[1]),
                radius=radius,  # Use the provided radius
                type='gas_station',
                rank_by='prominence'
            )
            print(f"   Raw places_nearby API result: {places_result}")

            if not places_result.get('results'):
                print(f"   No fuel stations found in 'results' key or 'results' is empty for {location} at {distance_km} km")
                # raise ValueError(f"No fuel stations found near {distance_km} km on the route") # Keep this commented for now to allow continuation
                return None # Explicitly return None if no results

            # Select the top-rated station
            station = places_result['results'][0]
            print(f"   Selected station (first result): {station.get('name')} at {station.get('geometry', {}).get('location')}")
            
            # Get detailed place information including address
            place_details = self.client.place(
                station['place_id'],
                fields=['name', 'rating', 'opening_hours', 'formatted_address', 'geometry', 'place_id']
            )['result']
            
            # Extract location from the detailed place information
            station_location = place_details['geometry']['location']
            print(f"Station details - Name: {place_details.get('name')}, Location: {station_location}")
            
            # Create Google Maps URL using place_id
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_details['place_id']}"
            
            return {
                "name": place_details.get('name', 'Unknown Fuel Station'),
                "rating": place_details.get('rating', 0.0),
                "is_open": place_details.get('opening_hours', {}).get('open_now', False),
                "address": place_details.get('formatted_address', 'Address not available'),
                "location": [
                    station_location['lat'],
                    station_location['lng']
                ],
                "maps_url": maps_url
            }

        except Exception as e:
            print(f"Error in get_fuel_station: {str(e)}")
            return None
    
    def get_nearest_city(self, lat, lng):
        """
        Get the nearest city name for given coordinates.
        Args:
            lat: Latitude
            lng: Longitude
        Returns:
            String with city name or None if not found
        """
        try:
            # Perform reverse geocoding
            result = self.client.reverse_geocode((lat, lng))
            
            if not result:
                return None
            
            # Look for city in address components
            for component in result[0]['address_components']:
                if 'locality' in component['types']:
                    return component['long_name']
                elif 'administrative_area_level_1' in component['types']:
                    return component['long_name']
            
            return None
            
        except Exception as e:
            print(f"Error getting nearest city: {str(e)}")
            return None 

    def get_restaurants(self, location, radius=5000):
        """
        Get restaurant options near a location
        Args:
            location: Tuple of (latitude, longitude)
            radius: Search radius in meters (default: 5000m = 5km)
        Returns:
            Dictionary with 'results' key containing list of restaurant dictionaries
        """
        try:
            print(f"\n=== Finding restaurants near {location} ===")
            print(f"Radius: {radius}m")
            
            # Search for restaurants
            response = self.client.places_nearby(
                location=location,
                radius=radius,
                type='restaurant',
                rank_by='prominence'
            )
            
            if not response.get('results'):
                print("No restaurants found")
                return {'results': []}
            
            # Get detailed information for each restaurant
            restaurants = []
            for place in response['results']:
                try:
                    # Get detailed place information
                    details = self.client.place(
                        place['place_id'],
                        fields=['name', 'rating', 'opening_hours', 'formatted_address', 
                               'geometry', 'place_id', 'price_level', 'business_status',
                               'formatted_phone_number', 'website', 'url']
                    )['result']
                    
                    # Create Google Maps URL using place_id
                    maps_url = f"https://www.google.com/maps/place/?q=place_id:{details['place_id']}"
                    
                    # Only include places that are restaurants or food-related
                    if any(food_type in place.get('types', []) for food_type in ['restaurant', 'food', 'meal_delivery', 'meal_takeaway']):
                        restaurant = {
                            'name': details.get('name', 'Unknown Restaurant'),
                            'rating': details.get('rating', 0.0),
                            'is_open': details.get('opening_hours', {}).get('open_now', False),
                            'address': details.get('formatted_address', 'Address not available'),
                            'location': [
                                details['geometry']['location']['lat'],
                                details['geometry']['location']['lng']
                            ],
                            'price_level': details.get('price_level', 0),
                            'business_status': details.get('business_status', 'UNKNOWN'),
                            'phone': details.get('formatted_phone_number', 'Not available'),
                            'website': details.get('website', 'Not available'),
                            'maps_url': maps_url
                        }
                        restaurants.append(restaurant)
                        print(f"Found restaurant: {restaurant['name']} ({restaurant['rating']} stars)")
                    
                except Exception as e:
                    print(f"Error getting details for restaurant {place.get('name')}: {str(e)}")
                    continue
            
            # Sort by rating
            restaurants.sort(key=lambda x: x.get('rating', 0), reverse=True)
            print(f"Found {len(restaurants)} restaurants")
            return {'results': restaurants}
            
        except Exception as e:
            print(f"Error finding restaurants: {str(e)}")
            return {'results': []}

    def get_city_coordinates(self, city_name):
        """
        Get coordinates for a city using Places API
        """
        try:
            print(f"\n=== Getting coordinates for city: {city_name} ===")
            
            # Add "India" to the search query for better results
            search_query = f"{city_name}, India"
            print(f"Search query: {search_query}")
            
            # Use text search to find the city
            response = self.client.places(
                query=search_query,
                type='locality',
                language='en'
            )
            
            if response.get('results'):
                location = response['results'][0]['geometry']['location']
                print(f"Found coordinates: {location}")
                return location
            else:
                print(f"No results found for city: {city_name}")
                return None
                
        except Exception as e:
            print(f"Error getting city coordinates: {str(e)}")
            return None 

    def find_nearby_places(self, location, radius=5000, type=None, keyword=None):
        """
        Find places near a location using Google Places API
        Args:
            location: Tuple of (latitude, longitude)
            radius: Search radius in meters (default 5000m)
            type: Optional place type (e.g., 'restaurant', 'food', 'lodging')
            keyword: Optional additional keyword for searching
        Returns:
            Dictionary with 'results' key containing list of place dictionaries
        """
        try:
            print(f"\n=== Finding nearby places near {location} ===")
            print(f"Radius: {radius}m, Type: {type}, Keyword: {keyword}")
            
            # Get city name for the location
            city_name = self.get_nearest_city(location[0], location[1])
            print(f"Location is in: {city_name}")
            
            # Perform the nearby search
            places_result = self.client.places_nearby(
                location=location,
                radius=radius,
                type=type,
                keyword=keyword,
                rank_by='prominence'
            )
            
            if not places_result or 'results' not in places_result:
                print("No places found")
                return {'results': []}
            
            # Process each place to get detailed information
            processed_places = []
            for place in places_result.get('results', []):
                try:
                    # Get place details
                    place_details = self.get_place_details(place['place_id'])
                    if place_details:
                        # Check if it's a restaurant based on type and services
                        is_restaurant = (
                            place_details.get('type') == 'restaurant' or
                            place_details.get('dine_in', False) or
                            any([
                                place_details.get('serves_breakfast', False),
                                place_details.get('serves_lunch', False),
                                place_details.get('serves_dinner', False)
                            ])
                        )
                        
                        if type in ['restaurant', 'food'] and not is_restaurant:
                            continue
                        
                        # Get place-specific city name if available, otherwise use the general location city
                        place_city = self.get_nearest_city(
                            place_details.get('geometry', {}).get('location', {}).get('lat', location[0]),
                            place_details.get('geometry', {}).get('location', {}).get('lng', location[1])
                        ) or city_name
                        
                        processed_place = {
                            'name': place_details.get('name', 'Unknown Place'),
                            'address': place_details.get('formatted_address', 'Address not available'),
                            'rating': place_details.get('rating', 0),
                            'is_open': place_details.get('opening_hours', {}).get('open_now', False),
                            'location': {
                                'lat': place_details.get('geometry', {}).get('location', {}).get('lat', 0),
                                'lng': place_details.get('geometry', {}).get('location', {}).get('lng', 0)
                            },
                            'maps_url': place_details.get('url', ''),
                            'phone': place_details.get('formatted_phone_number', 'Not available'),
                            'website': place_details.get('website', 'Not available'),
                            'price_level': place_details.get('price_level', 0),
                            'business_status': place_details.get('business_status', 'UNKNOWN'),
                            'dine_in': place_details.get('dine_in', False),
                            'serves_breakfast': place_details.get('serves_breakfast', False),
                            'serves_lunch': place_details.get('serves_lunch', False),
                            'serves_dinner': place_details.get('serves_dinner', False),
                            'city': place_city
                        }
                        processed_places.append(processed_place)
                        print(f"Found place: {processed_place['name']} in {place_city} ({processed_place['rating']} stars)")
                except Exception as e:
                    print(f"Error processing place details: {str(e)}")
                    continue
            
            # Sort places by rating
            processed_places.sort(key=lambda x: x.get('rating', 0), reverse=True)
            print(f"Found {len(processed_places)} places")
            return {'results': processed_places}
            
        except Exception as e:
            print(f"Error finding nearby places: {str(e)}")
            return {'results': []} 