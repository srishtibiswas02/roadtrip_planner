import json
import os
from datetime import datetime, time
from typing import Dict, List, Optional

class ProfileManager:
    def __init__(self):
        self.profiles_dir = "profiles"
        self.vehicle_profiles_dir = os.path.join(self.profiles_dir, "vehicles")
        self.user_profiles_dir = os.path.join(self.profiles_dir, "users")
        self._ensure_profiles_directory()
    
    def _ensure_profiles_directory(self):
        """Create profiles directory if it doesn't exist"""
        if not os.path.exists(self.profiles_dir):
            os.makedirs(self.profiles_dir)
        if not os.path.exists(self.vehicle_profiles_dir):
            os.makedirs(self.vehicle_profiles_dir)
        if not os.path.exists(self.user_profiles_dir):
            os.makedirs(self.user_profiles_dir)
    
    def save_vehicle_profile(self, profile_name: str, profile_data: Dict) -> bool:
        """Save a vehicle profile"""
        try:
            profile_data['last_updated'] = datetime.now().isoformat()
            file_path = os.path.join(self.vehicle_profiles_dir, f"{profile_name}.json")
            with open(file_path, 'w') as f:
                json.dump(profile_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving vehicle profile: {str(e)}")
            return False
    
    def save_user_profile(self, profile_name: str, profile_data: Dict) -> bool:
        """Save a user profile"""
        try:
            profile_data['last_updated'] = datetime.now().isoformat()
            file_path = os.path.join(self.user_profiles_dir, f"{profile_name}.json")
            with open(file_path, 'w') as f:
                json.dump(profile_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving user profile: {str(e)}")
            return False
    
    def load_vehicle_profile(self, profile_name: str) -> Optional[Dict]:
        """Load a vehicle profile"""
        try:
            file_path = os.path.join(self.vehicle_profiles_dir, f"{profile_name}.json")
            if not os.path.exists(file_path):
                return None
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading vehicle profile: {str(e)}")
            return None
    
    def load_user_profile(self, profile_name: str) -> Optional[Dict]:
        """Load a user profile"""
        try:
            file_path = os.path.join(self.user_profiles_dir, f"{profile_name}.json")
            if not os.path.exists(file_path):
                return None
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading user profile: {str(e)}")
            return None
    
    def list_vehicle_profiles(self) -> List[str]:
        """List all available vehicle profiles"""
        try:
            profiles = []
            for file in os.listdir(self.vehicle_profiles_dir):
                if file.endswith('.json'):
                    profiles.append(file[:-5])
            return profiles
        except Exception as e:
            print(f"Error listing vehicle profiles: {str(e)}")
            return []
    
    def list_user_profiles(self) -> List[str]:
        """List all available user profiles"""
        try:
            profiles = []
            for file in os.listdir(self.user_profiles_dir):
                if file.endswith('.json'):
                    profiles.append(file[:-5])
            return profiles
        except Exception as e:
            print(f"Error listing user profiles: {str(e)}")
            return []
    
    def delete_vehicle_profile(self, profile_name: str) -> bool:
        """Delete a vehicle profile"""
        try:
            file_path = os.path.join(self.vehicle_profiles_dir, f"{profile_name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting vehicle profile: {str(e)}")
            return False
    
    def delete_user_profile(self, profile_name: str) -> bool:
        """Delete a user profile"""
        try:
            file_path = os.path.join(self.user_profiles_dir, f"{profile_name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting user profile: {str(e)}")
            return False

class VehicleProfile:
    def __init__(self, name: str, vehicle_type: str, fuel_type: str, 
                 mileage: float, tank_size: float):
        self.name = name
        self.vehicle_type = vehicle_type
        self.fuel_type = fuel_type
        self.mileage = mileage
        self.tank_size = tank_size
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'vehicle_type': self.vehicle_type,
            'fuel_type': self.fuel_type,
            'mileage': self.mileage,
            'tank_size': self.tank_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VehicleProfile':
        return cls(
            name=data['name'],
            vehicle_type=data['vehicle_type'],
            fuel_type=data['fuel_type'],
            mileage=data['mileage'],
            tank_size=data['tank_size']
        )

class UserPreferences:
    def __init__(self, driving_hours_start: time, driving_hours_end: time,
                 breakfast_time: time, lunch_time: time, dinner_time: time):
        self.driving_hours_start = driving_hours_start
        self.driving_hours_end = driving_hours_end
        self.breakfast_time = breakfast_time
        self.lunch_time = lunch_time
        self.dinner_time = dinner_time
    
    def to_dict(self) -> Dict:
        return {
            'driving_hours_start': self.driving_hours_start.strftime('%H:%M'),
            'driving_hours_end': self.driving_hours_end.strftime('%H:%M'),
            'breakfast_time': self.breakfast_time.strftime('%H:%M'),
            'lunch_time': self.lunch_time.strftime('%H:%M'),
            'dinner_time': self.dinner_time.strftime('%H:%M')
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserPreferences':
        return cls(
            driving_hours_start=datetime.strptime(data['driving_hours_start'], '%H:%M').time(),
            driving_hours_end=datetime.strptime(data['driving_hours_end'], '%H:%M').time(),
            breakfast_time=datetime.strptime(data['breakfast_time'], '%H:%M').time(),
            lunch_time=datetime.strptime(data['lunch_time'], '%H:%M').time(),
            dinner_time=datetime.strptime(data['dinner_time'], '%H:%M').time()
        )

class UserProfile:
    def __init__(self, name: str, preferences: UserPreferences):
        self.name = name
        self.preferences = preferences
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'preferences': self.preferences.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserProfile':
        return cls(
            name=data['name'],
            preferences=UserPreferences.from_dict(data['preferences'])
        ) 