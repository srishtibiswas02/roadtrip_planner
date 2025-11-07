# Gemini API key (replace with your own key)
# Obtain from: https://makersuite.google.com/app/apikey
# Ensure the Gemini API is enabled in your Google Cloud project
GEMINI_API_KEY = "AIzaSyBEFkA6Qm4vo7bzRf25ZGoBw34TsUQHZHc"

import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional

# Load environment variables
load_dotenv()

# Override API key with environment variable if available
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', GEMINI_API_KEY)

def get_trip_suggestions(start, destination, distance_km):
    """
    Fetch personalized trip suggestions using Gemini API.
    Args:
        start: Starting city (e.g., 'Pune').
        destination: Destination city (e.g., 'Goa').
        distance_km: Total route distance in kilometers.
    Returns: Dict with scenic_routes, safety_tips, and hidden_gems.
    Raises: Exception on API errors (e.g., invalid key, no response, network issues).
    """
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY in llm.py or .env file.")

    try:
        # Configure Gemini API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro')

        # Construct prompt for trip suggestions
        prompt = f"""
        Provide personalized suggestions for a road trip from {start} to {destination} in India ({distance_km} km).
        Format the response as a JSON object with three keys:
        - "scenic_routes": A string describing scenic routes or detours to take.
        - "safety_tips": A string with safety tips for the trip (e.g., road conditions, emergency prep).
        - "hidden_gems": A string describing lesser-known attractions or stops along the route.
        Ensure the suggestions are specific to the route and practical for Indian roads.
        """
        
        # Generate response
        response = model.generate_content(prompt)
        
        if not response.text:
            raise ValueError("No suggestions returned by Gemini API")
        
        # Parse JSON response
        try:
            suggestions = json.loads(response.text.strip())
            if not all(key in suggestions for key in ['scenic_routes', 'safety_tips', 'hidden_gems']):
                raise ValueError("Invalid response format from Gemini API")
            return suggestions
        except json.JSONDecodeError:
            raise ValueError("Gemini API response is not valid JSON")
    
    except genai.types.generation_types.BlockedPromptException as e:
        raise Exception(f"Gemini API blocked prompt: {str(e)}")
    except genai.types.generation_types.StopCandidateException as e:
        raise Exception(f"Gemini API stopped generation: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error in Gemini API: {str(e)}")

def get_fuel_price_fallback(fuel_type='petrol'):
    """
    Fallback fuel price estimation using Gemini API.
    Args:
        fuel_type: 'petrol' or 'diesel'.
    Returns: Float representing fuel price (₹/litre).
    Raises: Exception on API errors.
    """
    if fuel_type not in ['petrol', 'diesel']:
        raise ValueError(f"Unsupported fuel type: {fuel_type}. Use 'petrol' or 'diesel'.")

    if not GEMINI_API_KEY:
        raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY in llm.py or .env file.")

    try:
        # Configure Gemini API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro')

        # Construct prompt for fuel price
        prompt = f"""
        Estimate the average {fuel_type} price per litre in India today, considering recent trends.
        Return only a single number (float) in ₹/litre, e.g., 100.50.
        """
        
        # Generate response
        response = model.generate_content(prompt)
        
        if not response.text:
            raise ValueError(f"No {fuel_type} price returned by Gemini API")
        
        # Parse response as float
        try:
            price = float(response.text.strip())
            if price <= 0:
                raise ValueError(f"Invalid {fuel_type} price returned by Gemini API")
            return price
        except ValueError:
            raise ValueError(f"Gemini API response is not a valid number for {fuel_type} price")
    
    except genai.types.generation_types.BlockedPromptException as e:
        raise Exception(f"Gemini API blocked prompt: {str(e)}")
    except genai.types.generation_types.StopCandidateException as e:
        raise Exception(f"Gemini API stopped generation: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error in Gemini API: {str(e)}")

class LLMService:
    def __init__(self):
        # Initialize Gemini API
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def get_sightseeing_spots(self, start_point: str, end_point: str) -> List[Dict]:
        """
        Get sightseeing spots between two points using Gemini API
        Args:
            start_point: Starting location
            end_point: Destination location
        Returns:
            List of dictionaries containing spot information
        """
        try:
            # Create a prompt for Gemini
            prompt = f"""
            Suggest 5-7 popular tourist attractions and sightseeing spots between {start_point} and {end_point} in India.
            For each spot, provide:
            1. Name
            2. Brief description (1-2 sentences)
            3. Type of attraction (e.g., Historical, Natural, Religious, etc.)
            4. Best time to visit
            Format the response as a JSON array of objects with these fields.
            Example format:
            [
                {{
                    "name": "Example Spot",
                    "description": "A brief description",
                    "type": "Historical",
                    "best_time": "Morning"
                }}
            ]
            IMPORTANT: Ensure the response is valid JSON with proper commas between objects and no trailing commas.
            """
            
            # Get response from Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Clean the response text to ensure it's valid JSON
            # Remove any markdown formatting or extra text
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Additional cleaning to ensure valid JSON
            # Remove any trailing commas in arrays
            response_text = response_text.replace(',]', ']')
            # Remove any trailing commas in objects
            response_text = response_text.replace(',}', '}')
            
            try:
                spots = json.loads(response_text)
                # Validate the structure of each spot
                if not isinstance(spots, list):
                    raise ValueError("Response is not a JSON array")
                
                for spot in spots:
                    if not isinstance(spot, dict):
                        raise ValueError("Spot is not a JSON object")
                    required_fields = ['name', 'description', 'type', 'best_time']
                    if not all(field in spot for field in required_fields):
                        raise ValueError(f"Spot missing required fields: {required_fields}")
                
                return spots
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
                print(f"Response text: {response_text}")
                return []
            
        except Exception as e:
            print(f"Error in get_sightseeing_spots: {str(e)}")
            return []
    
    def get_spot_details(self, spot_name: str, location: Dict[str, float], places_service, maps_service) -> Optional[Dict]:
        """
        Get additional details for a sightseeing spot
        Args:
            spot_name: Name of the spot
            location: Reference location for search (dict with 'lat' and either 'lng' or 'lon')
            places_service: PlacesService instance
            maps_service: MapsService instance
        Returns:
            Dictionary with spot details or None if not found
        """
        try:
            # Convert location format if needed
            search_location = {
                'lat': location['lat'],
                'lng': location.get('lng', location.get('lon'))  # Try 'lng' first, fall back to 'lon'
            }
            
            # Get coordinates for the spot using Places API
            place_result = places_service.client.places(
                query=spot_name,
                location=search_location,
                radius=50000  # 50km radius
            )
            
            if place_result.get('results'):
                place = place_result['results'][0]
                spot_location = place['geometry']['location']
                
                return {
                    'location': spot_location,
                    'maps_url': f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}"
                }
            
            return None
            
        except Exception as e:
            print(f"Error in get_spot_details: {str(e)}")
            return None 