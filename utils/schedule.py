from datetime import datetime, timedelta
from .maps import MapsService
from .places import PlacesService
from .fuel import FuelService
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

class SchedulePlanner:
    def __init__(self):
        self.maps_service = MapsService()
        self.places_service = PlacesService()
        self.fuel_service = FuelService()
        self.model = genai.GenerativeModel('gemini-pro-vision')
    
    def plan_schedule(self, start_point, end_point, departure_time, 
                     driving_hours_start, driving_hours_end,
                     breakfast_time, lunch_time, dinner_time,
                     vehicle_type, mileage, tank_size):
        """
        Plan the complete schedule for the trip
        """
        # Get route information
        directions = self.maps_service.get_directions(
            start_point, end_point,
            mode="driving",  # Use driving mode for both cars and bikes since motorbike mode is not supported by Google Maps API
            departure_time=departure_time
        )
        
        if not directions:
            return None
        
        route = directions[0]
        leg = route['legs'][0]
        total_duration = leg['duration']['value']  # in seconds
        total_distance = leg['distance']['value']  # in meters
        
        # Calculate rest stops first and store as instance variable
        self.rest_stops = self._calculate_rest_stops(
            departure_time, total_duration,
            driving_hours_start, driving_hours_end,
            leg['steps'], start_point, end_point, vehicle_type
        )
        
        # Calculate fuel stops
        fuel_stops = self._calculate_fuel_stops(
            total_distance, mileage, tank_size, leg['steps'], leg['end_address']
        )
        
        # Calculate meal stops (now has access to self.rest_stops)
        meal_stops = self._calculate_meal_stops(
            departure_time, total_duration,
            breakfast_time, lunch_time, dinner_time,
            leg['steps']
        )
        
        return {
            'total_duration': total_duration,
            'total_distance': total_distance,
            'fuel_stops': fuel_stops,
            'meal_stops': meal_stops,
            'rest_stops': self.rest_stops,
            'steps': leg['steps']
        }
    
    def _calculate_fuel_stops(self, total_distance, mileage, tank_size, steps, destination_address):
        """
        Calculate optimal fuel stops based on vehicle range
        Args:
            total_distance: Total distance of the trip in meters.
            mileage: Vehicle mileage in km/l.
            tank_size: Vehicle tank size in liters.
            steps: List of route steps from Google Maps API.
            destination_address: The final destination address string.
        """
        fuel_stops = []
        distance_covered_total = 0  # Total distance covered in the trip so far
        last_fuel_stop_distance = 0 # Distance at which the last refueling occurred
        current_fuel = tank_size      # Start with a full tank
        total_trip_fuel_cost = 0
        total_trip_fuel_used = 0

        # Calculate total fuel needed for the trip (for reference, not for stop logic)
        total_fuel_needed_for_trip = (total_distance / 1000) / mileage

        route_path = []
        for step in steps:
            route_path.append([step['start_location']['lat'], step['start_location']['lng']])
            route_path.append([step['end_location']['lat'], step['end_location']['lng']])

        print(f"\n=== Calculating fuel stops (New Strategy - Full Tank Start, Dest. Fill) ===")
        print(f"Total distance: {total_distance/1000:.1f} km, Mileage: {mileage} km/l, Tank: {tank_size} l")
        print(f"Estimated total fuel for trip: {total_fuel_needed_for_trip:.2f} liters")
        print(f"Starting with current_fuel (assumed full): {current_fuel:.2f} liters")

        # Iterate through steps to simulate travel and fuel consumption
        for i, step in enumerate(steps):
            # Capture state at the beginning of processing this step
            fuel_at_start_of_step = current_fuel
            distance_covered_at_start_of_step_m = distance_covered_total

            # Basic calculations for the current step
            step_distance_m = step['distance']['value']
            step_distance_km = step_distance_m / 1000
            fuel_needed_for_step = step_distance_km / mileage
            
            print(f"-- Step {i+1} ({step.get('html_instructions','').split('<div')[0][:30]}...): Dist: {step_distance_km:.2f}km, Fuel for step: {fuel_needed_for_step:.2f}l, Start Fuel: {fuel_at_start_of_step:.2f}l")
            # Ensure fuel_needed_for_step is not negative, though step_distance_km should always be positive
            fuel_needed_for_step = max(0, fuel_needed_for_step)
            print(f"   Processing Step {i+1}: step_dist_km={step_distance_km:.2f}, fuel_needed={fuel_needed_for_step:.2f}")

            perform_refuel_action = False
            search_location_for_station_km = 0
            fuel_level_at_search_trigger_for_refill_calc = 0 

            # 1. Proactive Check: Will completing this step drop fuel below 15%?
            if (fuel_at_start_of_step - fuel_needed_for_step) <= (tank_size * 0.15):
                perform_refuel_action = True
                # Calculate how far we can travel before hitting 15% fuel
                distance_can_travel_before_15_percent_km = max(0, (fuel_at_start_of_step - (tank_size * 0.15)) * mileage)
                # Calculate the exact point where we should search for a fuel station
                calculated_search_km = (distance_covered_at_start_of_step_m / 1000) + distance_can_travel_before_15_percent_km
                # Don't search beyond total trip distance
                search_location_for_station_km = min(calculated_search_km, total_distance / 1000)
                fuel_level_at_search_trigger_for_refill_calc = tank_size * 0.15
                print(f"   Proactive: Step requires {fuel_needed_for_step:.2f}L. Fuel will be low. Search around {search_location_for_station_km:.1f}km (orig calc: {calculated_search_km:.1f}km). Expected fuel for refill calc: {fuel_level_at_search_trigger_for_refill_calc:.2f}L.")
            
            current_fuel -= fuel_needed_for_step
            distance_covered_total += step_distance_m

            # 2. Reactive Check: Is fuel low *now* (if not caught by proactive)?
            if not perform_refuel_action and current_fuel <= (tank_size * 0.15):
                perform_refuel_action = True
                search_location_for_station_km = min(distance_covered_total / 1000, total_distance / 1000)
                fuel_level_at_search_trigger_for_refill_calc = current_fuel 
                print(f"   Reactive: Fuel IS low ({current_fuel:.2f}L) after step. Search at {search_location_for_station_km:.1f}km. Effective fuel for refill calc: {fuel_level_at_search_trigger_for_refill_calc:.2f}L")

            # 3. Additional Check: Will we have enough fuel to reach the next potential stop?
            if not perform_refuel_action and i < len(steps) - 1:
                next_step_distance = steps[i + 1]['distance']['value'] / 1000
                fuel_needed_for_next_step = next_step_distance / mileage
                if current_fuel - fuel_needed_for_next_step <= (tank_size * 0.15):
                    perform_refuel_action = True
                    search_location_for_station_km = min(distance_covered_total / 1000, total_distance / 1000)
                    fuel_level_at_search_trigger_for_refill_calc = current_fuel
                    print(f"   Next Step Check: Need {fuel_needed_for_next_step:.2f}L for next step. Current fuel {current_fuel:.2f}L would be too low. Search at {search_location_for_station_km:.1f}km.")

            print(f"   End of Step {i+1} processing: Current Total Dist: {distance_covered_total/1000:.2f}km, Fuel Left After Step: {current_fuel:.2f}l, Last Fuel Stop Dist: {last_fuel_stop_distance/1000:.2f}km")

            if perform_refuel_action and (search_location_for_station_km * 1000) > last_fuel_stop_distance: 
                print(f"   Attempting refuel. Search target: {search_location_for_station_km:.1f}km. Effective fuel for refill calc: {fuel_level_at_search_trigger_for_refill_calc:.2f}L.")
                
                try:
                    fuel_station = self.places_service.get_fuel_station(
                        distance_km=search_location_for_station_km,
                        route_path=route_path,
                        total_distance_km= total_distance / 1000 
                    )
                    print(f"   get_fuel_station returned: {'A station object' if fuel_station else 'None'}")

                    if fuel_station:
                        print(f"Found fuel station: {fuel_station['name']} at {fuel_station['location']}")
                        station_state = None
                        if 'address' in fuel_station:
                            state_mapping = { 'Andhra Pradesh': ['AP', 'Andhra'], 'Arunachal Pradesh': ['Arunachal'], 'Assam': [], 'Bihar': [], 'Chhattisgarh': ['CG'], 'Goa': [], 'Gujarat': ['GJ'], 'Haryana': ['HR'], 'Himachal Pradesh': ['HP', 'Himachal'], 'Jharkhand': ['JH'], 'Karnataka': ['KA'], 'Kerala': ['KL'], 'Madhya Pradesh': ['MP'], 'Maharashtra': ['MH'], 'Manipur': ['MN'], 'Meghalaya': ['ML'], 'Mizoram': ['MZ'], 'Nagaland': ['NL'], 'Odisha': ['OR', 'Orissa'], 'Punjab': ['PB'], 'Rajasthan': ['RJ'], 'Sikkim': ['SK'], 'Tamil Nadu': ['TN', 'Tamilnadu'], 'Telangana': ['TS', 'TG'], 'Tripura': ['TR'], 'Uttar Pradesh': ['UP'], 'Uttarakhand': ['UK', 'Uttaranchal'], 'West Bengal': ['WB', 'Bengal'], 'Delhi': ['NCT', 'New Delhi'], 'Chandigarh': ['CH'], 'Puducherry': ['PY', 'Pondicherry'], 'Jammu and Kashmir': ['JK', 'J&K'], 'Ladakh': ['LA'], 'Andaman and Nicobar Islands': ['AN'], 'Dadra and Nagar Haveli and Daman and Diu': ['DNHDD'], 'Lakshadweep': ['LD'] }
                            address_lower = fuel_station['address'].lower()
                            for name, variations in state_mapping.items():
                                if name.lower() in address_lower or any(v.lower() in address_lower for v in variations):
                                    station_state = name
                                    break
                        if not station_state: 
                            station_state = self.places_service.get_nearest_state(fuel_station['location'][0], fuel_station['location'][1])
                        
                        station_fuel_prices = self.fuel_service.get_fuel_prices(station_state)
                        if not station_fuel_prices:
                            print(f"Could not get fuel prices for {station_state}, using fallback prices")
                            station_fuel_prices = self.fuel_service._get_fallback_prices(station_state)
                        
                        price_per_liter_at_station = station_fuel_prices.get('petrol', 0)
                        
                        actual_fuel_at_pump_before_fill = max(0, fuel_level_at_search_trigger_for_refill_calc)
                        
                        # ALWAYS fill to 100% for intermediate stops.
                        fuel_to_add = tank_size - actual_fuel_at_pump_before_fill
                        fuel_to_add = max(0, fuel_to_add)
                        print(f"   Intermediate stop logic: Filling to 100%. Fuel to add: {fuel_to_add:.2f}L")
                        
                        cost_for_this_fill = fuel_to_add * price_per_liter_at_station
                        
                        refilled_fuel_level = actual_fuel_at_pump_before_fill + fuel_to_add
                        refilled_fuel_level = min(refilled_fuel_level, tank_size)
                        
                        total_trip_fuel_cost += cost_for_this_fill 
                        total_trip_fuel_used += fuel_to_add     
                        
                        distance_of_this_fuel_stop_m = search_location_for_station_km * 1000
                        
                        fuel_stops.append({
                            'location': fuel_station['location'],
                            'distance': distance_of_this_fuel_stop_m,
                            'distance_from_last': distance_of_this_fuel_stop_m - last_fuel_stop_distance,
                            'type': 'fuel',
                            'name': fuel_station['name'],
                            'rating': fuel_station.get('rating'),
                            'is_open': fuel_station.get('is_open'),
                            'address': fuel_station['address'],
                            'maps_url': fuel_station['maps_url'],
                            'state': station_state,
                            'fuel_prices': station_fuel_prices,
                            'segment_cost': cost_for_this_fill,
                            'segment_fuel': fuel_to_add,
                            'price_per_liter': price_per_liter_at_station,
                            'total_fuel_needed': total_fuel_needed_for_trip, 
                            'total_cost': total_trip_fuel_cost, 
                            'total_fuel_used': total_trip_fuel_used, 
                            'average_price_per_liter': total_trip_fuel_cost / total_trip_fuel_used if total_trip_fuel_used > 0 else 0,
                            'fuel_remaining': refilled_fuel_level, 
                            'fuel_remaining_percent': (refilled_fuel_level / tank_size) * 100,
                            'refill_amount': fuel_to_add,
                            'is_initial_stop': False
                        })
                        
                        current_fuel = refilled_fuel_level 
                        last_fuel_stop_distance = distance_of_this_fuel_stop_m

                        print(f"   Refueled at {fuel_station['name']}. Added {fuel_to_add:.2f}l. Fuel now: {current_fuel:.2f}l at {distance_of_this_fuel_stop_m/1000:.1f}km. Last stop updated to this station's distance.")
                    else:
                        print(f"   No fuel station found near {search_location_for_station_km:.1f} km. Continuing with current fuel ({current_fuel:.2f}L). Last stop dist remains {last_fuel_stop_distance/1000:.1f}km.")
                except Exception as e:
                    print(f"   Error during get_fuel_station call or processing its result: {str(e)}. Current fuel {current_fuel:.2f}L. Dist covered total {distance_covered_total/1000:.1f}km.")
            
            print(f"   After potential refuel action for step {i+1}: Final Current Fuel: {current_fuel:.2f}L, Final Total Dist: {distance_covered_total/1000:.2f}km")

        print(f"\nLoop finished. Calculated intermediate fuel stops: {len(fuel_stops)}")
        print(f"   Route total_distance: {total_distance/1000:.2f} km. Accumulated distance_covered_total: {distance_covered_total/1000:.2f} km.")
        print(f"   FINAL Fuel level before destination fill consideration: {current_fuel:.2f}L at {distance_covered_total/1000:.2f}km total distance.")
        
        # Add a final mandatory fill-up stop at the destination
        if steps: # Ensure there are steps to get destination info
            print(f"Adding mandatory final fill-up at destination.")
            destination_coords = steps[-1]['end_location']
            destination_distance_m = total_distance # The final stop is at the total distance

            # Fuel level upon arrival at destination BEFORE this final fill
            fuel_at_destination_before_final_fill = current_fuel 
            
            try:
                # Use Places API to find a fuel station near destination
                dest_fuel_station = self.places_service.get_fuel_station(
                    distance_km=total_distance / 1000,  # Convert to km
                    route_path=route_path,
                    total_distance_km=total_distance / 1000,
                    radius=10000  # 10km radius in meters
                )

                # Get state and fuel prices
                if dest_fuel_station:
                    dest_state = None
                    if 'address' in dest_fuel_station:
                        state_mapping = { 'Andhra Pradesh': ['AP', 'Andhra'], 'Arunachal Pradesh': ['Arunachal'], 'Assam': [], 'Bihar': [], 'Chhattisgarh': ['CG'], 'Goa': [], 'Gujarat': ['GJ'], 'Haryana': ['HR'], 'Himachal Pradesh': ['HP', 'Himachal'], 'Jharkhand': ['JH'], 'Karnataka': ['KA'], 'Kerala': ['KL'], 'Madhya Pradesh': ['MP'], 'Maharashtra': ['MH'], 'Manipur': ['MN'], 'Meghalaya': ['ML'], 'Mizoram': ['MZ'], 'Nagaland': ['NL'], 'Odisha': ['OR', 'Orissa'], 'Punjab': ['PB'], 'Rajasthan': ['RJ'], 'Sikkim': ['SK'], 'Tamil Nadu': ['TN', 'Tamilnadu'], 'Telangana': ['TS', 'TG'], 'Tripura': ['TR'], 'Uttar Pradesh': ['UP'], 'Uttarakhand': ['UK', 'Uttaranchal'], 'West Bengal': ['WB', 'Bengal'], 'Delhi': ['NCT', 'New Delhi'], 'Chandigarh': ['CH'], 'Puducherry': ['PY', 'Pondicherry'], 'Jammu and Kashmir': ['JK', 'J&K'], 'Ladakh': ['LA'], 'Andaman and Nicobar Islands': ['AN'], 'Dadra and Nagar Haveli and Daman and Diu': ['DNHDD'], 'Lakshadweep': ['LD'] }
                        address_lower = dest_fuel_station['address'].lower()
                        for name, variations in state_mapping.items():
                            if name.lower() in address_lower or any(v.lower() in address_lower for v in variations):
                                dest_state = name
                                break
                    if not dest_state:
                        dest_state = self.places_service.get_nearest_state(dest_fuel_station['location'][0], dest_fuel_station['location'][1])
                else:
                    dest_state = self.places_service.get_nearest_state(destination_coords['lat'], destination_coords['lng'])

                dest_fuel_prices = self.fuel_service.get_fuel_prices(dest_state)
                if not dest_fuel_prices:
                    print(f"Could not get fuel prices for destination state {dest_state}, using fallback prices")
                    dest_fuel_prices = self.fuel_service._get_fallback_prices(dest_state)
                
                price_per_liter_at_dest = dest_fuel_prices.get('petrol', 0)
                fuel_to_add_at_dest = tank_size - fuel_at_destination_before_final_fill
                fuel_to_add_at_dest = max(0, fuel_to_add_at_dest)
                cost_for_dest_fill = fuel_to_add_at_dest * price_per_liter_at_dest
                
                total_trip_fuel_cost += cost_for_dest_fill
                total_trip_fuel_used += fuel_to_add_at_dest
                
                refilled_fuel_level_at_dest = fuel_at_destination_before_final_fill + fuel_to_add_at_dest
                refilled_fuel_level_at_dest = min(refilled_fuel_level_at_dest, tank_size)

                distance_from_actual_last_stop_m = destination_distance_m
                if fuel_stops:
                    distance_from_actual_last_stop_m = destination_distance_m - fuel_stops[-1]['distance']
                elif last_fuel_stop_distance == 0:
                    distance_from_actual_last_stop_m = destination_distance_m

                # Create the destination fuel stop entry
                dest_fuel_stop = {
                    'distance': destination_distance_m,
                    'distance_from_last': distance_from_actual_last_stop_m,
                    'type': 'fuel',
                    'state': dest_state,
                    'fuel_prices': dest_fuel_prices,
                    'segment_cost': cost_for_dest_fill,
                    'segment_fuel': fuel_to_add_at_dest,
                    'price_per_liter': price_per_liter_at_dest,
                    'total_fuel_needed': total_fuel_needed_for_trip,
                    'total_cost': total_trip_fuel_cost,
                    'total_fuel_used': total_trip_fuel_used,
                    'average_price_per_liter': total_trip_fuel_cost / total_trip_fuel_used if total_trip_fuel_used > 0 else 0,
                    'fuel_remaining': refilled_fuel_level_at_dest,
                    'fuel_remaining_percent': (refilled_fuel_level_at_dest / tank_size) * 100,
                    'refill_amount': fuel_to_add_at_dest,
                    'is_initial_stop': False,
                    'is_destination_stop': True
                }

                # Add station-specific information if available
                if dest_fuel_station:
                    dest_fuel_stop.update({
                        'location': dest_fuel_station['location'],
                        'name': dest_fuel_station['name'],
                        'address': dest_fuel_station['address'],
                        'maps_url': dest_fuel_station['maps_url'],
                        'rating': dest_fuel_station.get('rating'),
                        'is_open': dest_fuel_station.get('is_open')
                    })
                else:
                    # For fallback case, try to get rating and open status from a nearby station
                    try:
                        nearby_station = self.places_service.get_fuel_station(
                            distance_km=total_distance / 1000,
                            route_path=route_path,
                            total_distance_km=total_distance / 1000,
                            radius=10000  # 10km radius
                        )
                        if nearby_station:
                            dest_fuel_stop.update({
                                'location': destination_coords,
                                'name': f"Fill-up at Destination ({destination_address.split(',')[0]})",
                                'address': f"Final refuel at {destination_address}",
                                'maps_url': f"https://www.google.com/maps?q={destination_coords['lat']},{destination_coords['lng']}",
                                'rating': nearby_station.get('rating'),
                                'is_open': nearby_station.get('is_open')
                            })
                        else:
                            dest_fuel_stop.update({
                                'location': destination_coords,
                                'name': f"Fill-up at Destination ({destination_address.split(',')[0]})",
                                'address': f"Final refuel at {destination_address}",
                                'maps_url': f"https://www.google.com/maps?q={destination_coords['lat']},{destination_coords['lng']}"
                            })
                    except Exception as e:
                        print(f"Error getting nearby station details: {str(e)}")
                        dest_fuel_stop.update({
                            'location': destination_coords,
                            'name': f"Fill-up at Destination ({destination_address.split(',')[0]})",
                            'address': f"Final refuel at {destination_address}",
                            'maps_url': f"https://www.google.com/maps?q={destination_coords['lat']},{destination_coords['lng']}"
                        })

                # Always add the destination stop
                fuel_stops.append(dest_fuel_stop)
                print(f"Added destination fuel stop at {destination_distance_m/1000:.1f}km")

            except Exception as e:
                print(f"Error finding destination fuel station: {str(e)}")
                # Fallback to original destination coordinates
                dest_state = self.places_service.get_nearest_state(destination_coords['lat'], destination_coords['lng'])
                dest_fuel_prices = self.fuel_service.get_fuel_prices(dest_state)
                if not dest_fuel_prices:
                    print(f"Could not get fuel prices for destination state {dest_state}, using fallback prices")
                    dest_fuel_prices = self.fuel_service._get_fallback_prices(dest_state)
                
                price_per_liter_at_dest = dest_fuel_prices.get('petrol', 0)
                fuel_to_add_at_dest = tank_size - fuel_at_destination_before_final_fill
                fuel_to_add_at_dest = max(0, fuel_to_add_at_dest)
                cost_for_dest_fill = fuel_to_add_at_dest * price_per_liter_at_dest
                
                total_trip_fuel_cost += cost_for_dest_fill
                total_trip_fuel_used += fuel_to_add_at_dest
                
                refilled_fuel_level_at_dest = fuel_at_destination_before_final_fill + fuel_to_add_at_dest
                refilled_fuel_level_at_dest = min(refilled_fuel_level_at_dest, tank_size)

                distance_from_actual_last_stop_m = destination_distance_m
                if fuel_stops:
                    distance_from_actual_last_stop_m = destination_distance_m - fuel_stops[-1]['distance']
                elif last_fuel_stop_distance == 0:
                    distance_from_actual_last_stop_m = destination_distance_m

                # Always add the destination stop, even in fallback case
                fuel_stops.append({
                    'location': destination_coords,
                    'distance': destination_distance_m,
                    'distance_from_last': distance_from_actual_last_stop_m,
                    'type': 'fuel',
                    'name': f"Fill-up at Destination ({destination_address.split(',')[0]})",
                    'address': f"Final refuel at {destination_address}",
                    'maps_url': f"https://www.google.com/maps?q={destination_coords['lat']},{destination_coords['lng']}",
                    'state': dest_state,
                    'fuel_prices': dest_fuel_prices,
                    'segment_cost': cost_for_dest_fill,
                    'segment_fuel': fuel_to_add_at_dest,
                    'price_per_liter': price_per_liter_at_dest,
                    'total_fuel_needed': total_fuel_needed_for_trip,
                    'total_cost': total_trip_fuel_cost,
                    'total_fuel_used': total_trip_fuel_used,
                    'average_price_per_liter': total_trip_fuel_cost / total_trip_fuel_used if total_trip_fuel_used > 0 else 0,
                    'fuel_remaining': refilled_fuel_level_at_dest,
                    'fuel_remaining_percent': (refilled_fuel_level_at_dest / tank_size) * 100,
                    'refill_amount': fuel_to_add_at_dest,
                    'is_initial_stop': False,
                    'is_destination_stop': True
                })
                print(f"Added fallback destination fuel stop at {destination_distance_m/1000:.1f}km")

        print(f"Total fuel stops (incl. destination): {len(fuel_stops)}")
        return fuel_stops
    
    def _calculate_meal_stops(self, departure_time, total_duration,
                            breakfast_time, lunch_time, dinner_time, steps):
        """
        Calculate meal stops based on preferred meal times with specific durations:
        - Breakfast: 30 minutes
        - Lunch: 1 hour
        - Dinner: 1 hour
        Show all meal stops but only calculate durations for stops outside rest times.
        """
        meal_stops = []
        current_time = departure_time
        distance_covered = 0
        last_stop_distance = 0  # Track the last stop's distance
        
        # Calculate total distance from steps
        total_distance = sum(step['distance']['value'] for step in steps)
        
        # Define meal durations
        meal_durations = {
            'Breakfast': timedelta(minutes=30),
            'Lunch': timedelta(hours=1),
            'Dinner': timedelta(hours=1)
        }
        
        print(f"\n=== Calculating Meal Stops ===")
        print(f"Departure: {departure_time}")
        print(f"Meal times - Breakfast: {breakfast_time} (30min), Lunch: {lunch_time} (1hr), Dinner: {dinner_time} (1hr)")
        print(f"Total distance: {total_distance/1000:.1f}km")
        
        # Calculate all possible meal times for the trip duration
        total_days = (total_duration // (24 * 3600)) + 2  # Add 2 to include partial days and buffer
        all_meal_times = []
        
        # Generate meal times for each day
        for day in range(total_days):
            current_date = departure_time.date() + timedelta(days=day)
            # Add breakfast time
            all_meal_times.append({
                'time': datetime.combine(current_date, breakfast_time),
                'type': 'Breakfast',
                'day': day + 1
            })
            # Add lunch time
            all_meal_times.append({
                'time': datetime.combine(current_date, lunch_time),
                'type': 'Lunch',
                'day': day + 1
            })
            # Add dinner time
            all_meal_times.append({
                'time': datetime.combine(current_date, dinner_time),
                'type': 'Dinner',
                'day': day + 1
            })
        
        # Sort meal times chronologically
        all_meal_times.sort(key=lambda x: x['time'])
        
        # Track which meal times have been processed
        processed_meal_times = set()
        
        # Process each step and check for meal times
        for i, step in enumerate(steps):
            step_duration = step['duration']['value']
            step_distance = step['distance']['value']
            step_start_time = current_time
            step_end_time = current_time + timedelta(seconds=step_duration)
            step_start_distance = distance_covered
            step_end_distance = distance_covered + step_distance
            
            # Check if any meal time falls within this step or between steps
            for meal_info in all_meal_times:
                meal_time = meal_info['time']
                meal_type = meal_info['type']
                day_number = meal_info['day']
                
                # Skip if this meal time has already been processed
                meal_key = f"{day_number}_{meal_type}"
                if meal_key in processed_meal_times:
                    continue
                
                # Check if meal time falls within this step or between steps
                if (step_start_time <= meal_time <= step_end_time) or \
                   (i > 0 and steps[i-1]['end_location'] == step['start_location'] and \
                    meal_time > step_start_time - timedelta(minutes=30) and \
                    meal_time < step_end_time + timedelta(minutes=30)):
                    
                    # Determine the location for the meal stop
                    if step_start_time <= meal_time <= step_end_time:
                        # If meal time is within this step, interpolate the location
                        time_ratio = (meal_time - step_start_time).total_seconds() / step_duration
                        loc = {
                            'lat': step['start_location']['lat'] + (step['end_location']['lat'] - step['start_location']['lat']) * time_ratio,
                            'lng': step['start_location']['lng'] + (step['end_location']['lng'] - step['start_location']['lng']) * time_ratio
                        }
                        meal_distance = step_start_distance + (step_end_distance - step_start_distance) * time_ratio
                    else:
                        # If meal time is between steps, use the end location of the previous step
                        loc = step['start_location']
                        meal_distance = step_start_distance
                    
                    # Get city name using Places API
                    city = None
                    try:
                        # First try to get the city name from the location
                        reverse_geocode = self.maps_service.get_reverse_geocode(loc['lat'], loc['lng'])
                        if reverse_geocode and 'results' in reverse_geocode:
                            # Look for administrative_area_level_2 (city) first
                            for component in reverse_geocode['results'][0]['address_components']:
                                if 'administrative_area_level_2' in component['types']:
                                    city = component['long_name']
                                    break
                            # If no city found, try locality
                            if not city:
                                for component in reverse_geocode['results'][0]['address_components']:
                                    if 'locality' in component['types']:
                                        city = component['long_name']
                                        break
                        
                        # If no city found, try Places API nearby search
                        if not city:
                            nearby_places = self.places_service.find_nearby_places(
                                location=(loc['lat'], loc['lng']),
                                radius=5000,  # 5km radius
                                type='locality'  # Search for cities/towns
                            )
                            if nearby_places and 'results' in nearby_places and nearby_places['results']:
                                city = nearby_places['results'][0]['name']
                    except Exception as e:
                        print(f"Error getting city name: {str(e)}")
                    
                    # Get restaurant options near this location
                    restaurant_options = []
                    try:
                        # Try multiple search strategies to find restaurants
                        search_strategies = [
                            # Strategy 1: Direct restaurant search with small radius
                            {'type': 'restaurant', 'keyword': None, 'radius': 2000},
                            # Strategy 2: Food search with restaurant keyword
                            {'type': 'food', 'keyword': 'restaurant', 'radius': 2000},
                            # Strategy 3: Broader food search
                            {'type': 'food', 'keyword': None, 'radius': 2000},
                            # Strategy 4: Increased radius searches
                            {'type': 'restaurant', 'keyword': None, 'radius': 5000},
                            {'type': 'food', 'keyword': 'restaurant', 'radius': 5000},
                            {'type': 'food', 'keyword': None, 'radius': 5000}
                        ]
                        
                        # Try each search strategy until we find enough restaurants
                        for strategy in search_strategies:
                            if len(restaurant_options) >= 3:
                                break
                                
                            print(f"\nTrying search strategy: type={strategy['type']}, keyword={strategy['keyword']}, radius={strategy['radius']/1000:.1f}km")
                            
                            # Use the exact meal stop location for search
                            search_location = [loc['lat'], loc['lng']]
                            
                            # Search for places
                            places = self.places_service.find_nearby_places(
                                location=(search_location[0], search_location[1]),
                                radius=strategy['radius'],
                                type=strategy['type'],
                                keyword=strategy['keyword']
                            )
                            
                            if places and isinstance(places, dict) and 'results' in places and places['results']:
                                # Filter places to ensure they're within the search radius
                                valid_places = []
                                for place in places['results']:
                                    if isinstance(place, dict) and 'location' in place:
                                        # Calculate distance from place to meal stop
                                        dist = self._calculate_distance(
                                            place['location']['lat'],
                                            place['location']['lng'],
                                            search_location[0],
                                            search_location[1]
                                        ) / 1000  # Convert to km
                                        
                                        if dist <= strategy['radius']/1000:  # Within search radius
                                            # Add distance to the place info
                                            place['distance_from_route'] = dist
                                            valid_places.append(place)
                                
                                if valid_places:
                                    # Sort by rating and distance
                                    valid_places.sort(key=lambda x: (
                                        x.get('rating', 0),
                                        -x.get('distance_from_route', float('inf'))
                                    ), reverse=True)
                                    
                                    # Add unique places to options
                                    for place in valid_places:
                                        if len(restaurant_options) >= 3:
                                            break
                                            
                                        # Check if this place is already in options
                                        is_duplicate = False
                                        for existing in restaurant_options:
                                            if existing.get('name') == place.get('name'):
                                                is_duplicate = True
                                                break
                                        
                                        if not is_duplicate:
                                            restaurant_options.append(place)
                            
                            print(f"Found {len(restaurant_options)} restaurants so far")
                        
                        # If we still don't have enough restaurants, try one final search
                        if len(restaurant_options) < 3:
                            print("\nTrying final search with 10km radius")
                            # Use the meal stop location for the final search
                            food_places = self.places_service.find_nearby_places(
                                location=(loc['lat'], loc['lng']),
                                radius=10000,  # 10km radius
                                type='food'
                            )
                            
                            if food_places and isinstance(food_places, dict) and 'results' in food_places and food_places['results']:
                                # Filter and sort places
                                valid_places = []
                                for place in food_places['results']:
                                    if isinstance(place, dict) and 'location' in place:
                                        dist = self._calculate_distance(
                                            place['location']['lat'],
                                            place['location']['lng'],
                                            loc['lat'],
                                            loc['lng']
                                        ) / 1000  # Convert to km
                                        
                                        if dist <= 10:  # Within 10km
                                            place['distance_from_route'] = dist
                                            valid_places.append(place)
                                
                                if valid_places:
                                    valid_places.sort(key=lambda x: (
                                        x.get('rating', 0),
                                        -x.get('distance_from_route', float('inf'))
                                    ), reverse=True)
                                    
                                    for place in valid_places:
                                        if len(restaurant_options) >= 3:
                                            break
                                            
                                        is_duplicate = False
                                        for existing in restaurant_options:
                                            if existing.get('name') == place.get('name'):
                                                is_duplicate = True
                                                break
                                        
                                        if not is_duplicate:
                                            restaurant_options.append(place)
                    
                    except Exception as e:
                        print(f"Error fetching restaurants: {str(e)}")
                        # Add default options if we encounter an error
                        while len(restaurant_options) < 3:
                            restaurant_options.append({
                                'name': 'No additional restaurants found nearby',
                                'address': 'Please plan to bring food or search manually',
                                'rating': 0,
                                'is_open': False,
                                'maps_url': f"https://www.google.com/maps?q={loc['lat']},{loc['lng']}",
                                'note': f'No additional restaurants found within 50km of route (Suggestion {len(restaurant_options) + 1}/3)'
                            })
                    
                    # If we still don't have enough restaurants, add default options
                    if len(restaurant_options) < 3:
                        print(f"Could only find {len(restaurant_options)} restaurants within 50km of route")
                        # Add default options to reach 3 suggestions
                        while len(restaurant_options) < 3:
                            restaurant_options.append({
                                'name': 'No additional restaurants found nearby',
                                'address': 'Please plan to bring food or search manually',
                                'rating': 0,
                                'is_open': False,
                                'maps_url': f"https://www.google.com/maps?q={loc['lat']},{loc['lng']}",
                                'note': f'No additional restaurants found within 50km of route (Suggestion {len(restaurant_options) + 1}/3)'
                            })
                    
                    # Check if this meal time falls within a rest period
                    is_within_rest = False
                    for rest_stop in self.rest_stops:
                        if rest_stop['type'] == 'rest' and not rest_stop.get('is_destination'):
                            rest_start = rest_stop['time']
                            rest_end = rest_stop['next_day_start']
                            if rest_start <= meal_time <= rest_end:
                                is_within_rest = True
                                break
                    
                    # Calculate meal end time based on meal type (only if not within rest period)
                    meal_end_time = None
                    if not is_within_rest:
                        meal_end_time = meal_time + meal_durations[meal_type]
                    
                    # Add the meal stop
                    meal_stops.append({
                        'location': loc,
                        'time': meal_time,
                        'end_time': meal_end_time,
                        'distance': meal_distance,
                        'distance_from_last': meal_distance - last_stop_distance,
                        'type': 'meal',
                        'meal_type': meal_type,
                        'duration': meal_durations[meal_type] if not is_within_rest else None,
                        'restaurant_options': restaurant_options,
                        'city': city,
                        'is_within_rest': is_within_rest,
                        'day': day_number
                    })
                    
                    # Mark this meal time as processed
                    processed_meal_times.add(meal_key)
                    
                    print(f"Added Day {day_number} {meal_type} stop at {loc} with {len(restaurant_options)} restaurants")
                    if not is_within_rest:
                        print(f"Meal duration: {meal_durations[meal_type]}")
                    else:
                        print("Meal stop is within rest period - no duration calculated")
                    
                    last_stop_distance = meal_distance
            
            # Update current time and distance for next step
            current_time = step_end_time
            distance_covered = step_end_distance
        
        # Sort meal stops by day and time
        meal_stops.sort(key=lambda x: (x['day'], x['time']))
        
        print(f"\nTotal meal stops calculated: {len(meal_stops)}")
        return meal_stops
    
    def _calculate_rest_stops(self, departure_time, total_duration,
                            driving_hours_start, driving_hours_end, steps,
                            start_point, end_point, vehicle_type):
        """
        Calculate rest stops using ETA from route steps to find the place where the ETA matches the rest time, and fetch hotels there.
        """
        rest_stops = []
        current_time = departure_time
        distance_covered = 0
        last_stop_distance = 0
        total_time_needed = timedelta(seconds=total_duration)  # Convert to timedelta
        
        # Convert driving hours to datetime objects for easier comparison
        driving_start = datetime.combine(datetime.today(), driving_hours_start)
        driving_end = datetime.combine(datetime.today(), driving_hours_end)
        driving_duration = (driving_end - driving_start).total_seconds()
        
        print(f"\n=== Calculating Rest Stops (ETA-based, Places API) ===")
        print(f"Start: {start_point}, End: {end_point}")
        print(f"Departure: {departure_time}, Vehicle: {vehicle_type}")
        print(f"Driving hours: {driving_hours_start} to {driving_hours_end}")
        
        seconds_driven_today = 0
        for i, step in enumerate(steps):
            step_duration = step['duration']['value']
            step_distance = step['distance']['value']
            distance_covered += step_distance
            seconds_driven_today += step_duration
            current_time += timedelta(seconds=step_duration)
            
            is_last_step = (i == len(steps) - 1)
            current_time_of_day = current_time.time()
            
            # Check if we need to stop for rest
            need_rest = False
            if is_last_step:
                need_rest = True
            elif current_time_of_day >= driving_hours_end:
                need_rest = True
            elif seconds_driven_today >= driving_duration:
                need_rest = True
            
            if need_rest:
                loc = step['end_location']
                
                # Get city name using Places API
                city = None
                try:
                    # First try to get the city name from the step's end location
                    reverse_geocode = self.maps_service.get_reverse_geocode(loc['lat'], loc['lng'])
                    if reverse_geocode and 'results' in reverse_geocode:
                        # Look for administrative_area_level_2 (city) first
                        for component in reverse_geocode['results'][0]['address_components']:
                            if 'administrative_area_level_2' in component['types']:
                                city = component['long_name']
                                break
                        # If no city found, try locality
                        if not city:
                            for component in reverse_geocode['results'][0]['address_components']:
                                if 'locality' in component['types']:
                                    city = component['long_name']
                                    break
                    
                    # If no city found, try Places API nearby search
                    if not city:
                        nearby_places = self.places_service.find_nearby_places(
                            location=(loc['lat'], loc['lng']),
                            radius=5000,  # 5km radius
                            type='locality'  # Search for cities/towns
                        )
                        if nearby_places and 'results' in nearby_places and nearby_places['results']:
                            city = nearby_places['results'][0]['name']
                except Exception as e:
                    print(f"Error getting city name: {str(e)}")
                    
                # Always fetch hotels for every stop
                try:
                    # Fetch hotels with a larger radius if no city found
                    radius = 20000 if not city else 10000  # 20km if no city, 10km if city found
                    hotels = self.places_service.find_hotels(
                        location=(loc['lat'], loc['lng']),
                        radius=radius,
                        min_rating=3.5
                    )
                    
                    sorted_hotels = []
                    if hotels and 'results' in hotels:
                        sorted_hotels = sorted(
                            hotels['results'],
                            key=lambda x: x.get('rating', 0),
                            reverse=True
                        )[:3]
                        
                        hotel_options = []
                        for hotel in sorted_hotels:
                            try:
                                place_details = self.places_service.get_place_details(hotel['place_id'])
                                if place_details:
                                    # If we still don't have a city name, try to extract it from the hotel address
                                    if not city and 'formatted_address' in place_details:
                                        address = place_details['formatted_address']
                                        # Look for city name in the address (usually after the street address)
                                        address_parts = address.split(',')
                                        for part in address_parts:
                                            part = part.strip()
                                            # Skip if it's a state, country, or street-related terms
                                            if any(term in part.lower() for term in ['state', 'province', 'india', 'road', 'street', 'st', 'rd', 'plot', 'no.', 'infront', 'near', 'hotel', 'inn', 'residence', 'stay']):
                                                continue
                                            # If it's not a number and not too short, it might be a city
                                            if not part.isdigit() and len(part) > 2:
                                                # Additional check to ensure it's not a street name or hotel name
                                                if not any(term in part.lower() for term in ['lane', 'avenue', 'colony', 'sector', 'block', 'nagar', 'park', 'station', 'railway', 'sagar', 'agar', 'haram', 'peta', 'pet', 'puram', 'nagar', 'colony']):
                                                    # Check if this part looks like a city name (not a hotel name or street)
                                                    if not any(word in part.lower() for word in ['hotel', 'inn', 'residence', 'stay', 'grand', 'luxury']):
                                                        city = part
                                                        break
                                
                                    hotel_options.append({
                                        'name': place_details.get('name', 'Unknown Hotel'),
                                        'address': place_details.get('formatted_address', 'Address not available'),
                                        'rating': place_details.get('rating', 0),
                                        'is_open': place_details.get('opening_hours', {}).get('open_now', False),
                                        'maps_url': place_details.get('url', ''),
                                        'phone': place_details.get('formatted_phone_number', 'Not available'),
                                        'website': place_details.get('website', 'Not available'),
                                        'price_level': place_details.get('price_level', 0),
                                        'amenities': place_details.get('amenities', [])
                                    })
                            except Exception as e:
                                print(f"Error getting hotel details: {str(e)}")
                                continue
                except Exception as e:
                    print(f"Error fetching hotels: {str(e)}")
                    hotel_options = []
                
                if is_last_step:
                    # Last stop: destination, no resume journey fields
                    rest_stop = {
                        'location': loc,
                        'time': current_time,
                        'distance': distance_covered,
                        'distance_from_last': distance_covered - last_stop_distance,
                        'type': 'rest',
                        'hotel_options': hotel_options,
                        'is_destination': True,
                        'total_time_needed': total_time_needed,
                        'city': city
                    }
                else:
                        # Calculate next day's start time
                    next_day = current_time.date() + timedelta(days=1)
                    next_day_start = datetime.combine(next_day, driving_hours_start)
                    
                    # Calculate rest duration
                    rest_duration = next_day_start - current_time
                    total_time_needed += rest_duration
                        
                    rest_stop = {
                        'location': loc,
                        'time': current_time,
                        'distance': distance_covered,
                        'distance_from_last': distance_covered - last_stop_distance,
                            'type': 'rest',
                            'hotel_options': hotel_options,
                            'is_overnight': True,
                        'next_day_start': next_day_start,
                        'rest_duration': rest_duration,
                        'total_time_needed': total_time_needed,
                        'city': city
                    }
                        
                    rest_stops.append(rest_stop)
                print(f"Added rest stop at {loc} with {len(hotel_options)} hotels")
                if not is_last_step:
                    print(f"Rest duration: {rest_stop.get('rest_duration')}")
                print(f"Total time needed so far: {total_time_needed}")
                
                last_stop_distance = distance_covered
                if not is_last_step:
                    current_time = next_day_start
                    seconds_driven_today = 0  # Reset for next driving day
        
        print(f"\nTotal rest stops calculated: {len(rest_stops)}")
        print(f"Final total time needed: {total_time_needed}")
        return rest_stops
    
    def _calculate_distance(self, lat1, lng1, lat2, lng2):
        """
        Calculate distance between two points using Haversine formula
        """
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth's radius in meters
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
    
    def _get_optimal_rest_cities(self, start_point, end_point, departure_time, vehicle_type):
        """
        Get optimal rest stop cities using Gemini API
        """
        try:
            print(f"\n=== Getting optimal rest cities from Gemini API ===")
            print(f"Start: {start_point}, End: {end_point}")
            print(f"Departure: {departure_time}, Vehicle: {vehicle_type}")
            
            prompt = f"""
            I am planning a road trip from {start_point} to {end_point} in a {vehicle_type}.
            I will depart at {departure_time.strftime('%H:%M')}.
            Please suggest 2-3 optimal cities for overnight stays along this route.
            Consider:
            1. Safe and well-connected cities
            2. Good hotel availability
            3. Reasonable driving distances between stops
            4. Popular tourist destinations if possible
            
            Format the response as a list of cities only, one per line.
            Example:
            City1
            City2
            City3
            """
            
            print("Sending prompt to Gemini API...")
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                print("Error: Empty response from Gemini API")
                return None
                
            print(f"Gemini API Response: {response.text}")
            
            # Parse cities from response
            cities = []
            for line in response.text.split('\n'):
                line = line.strip()
                if line and not line.startswith(('Example:', 'City')):
                    cities.append(line)
            
            print(f"Parsed cities: {cities}")
            
            if not cities:
                print("Warning: No cities returned from Gemini API")
                return None
                
            return cities
            
        except Exception as e:
            print(f"Error getting optimal rest cities: {str(e)}")
            return None
    
    def _is_meal_time(self, current_time, breakfast_time, lunch_time, dinner_time):
        """
        Check if current time is close to any meal time
        """
        # Convert meal times to datetime objects for comparison
        current_date = current_time.date()
        meal_times = [
            datetime.combine(current_date, breakfast_time),
            datetime.combine(current_date, lunch_time),
            datetime.combine(current_date, dinner_time)
        ]
        
        for meal_time in meal_times:
            if abs((current_time - meal_time).total_seconds()) < 1800:  # 30 minutes window
                return True
        return False
    
    def _is_within_driving_hours(self, current_time, start_time, end_time):
        """
        Check if current time is within preferred driving hours
        """
        current_time = current_time.time()
        return start_time <= current_time <= end_time 