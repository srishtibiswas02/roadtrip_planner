import os
import json
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Dict, Tuple

class AuthManager:
    def __init__(self):
        self.users_dir = "users"
        self._ensure_users_directory()
    
    def _ensure_users_directory(self):
        """Create users directory if it doesn't exist"""
        if not os.path.exists(self.users_dir):
            os.makedirs(self.users_dir)
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return hashed, salt
    
    def register_user(self, username: str, password: str, email: str) -> bool:
        """Register a new user"""
        try:
            # Check if user already exists
            if self.get_user(username):
                return False
            
            # Hash password
            hashed_password, salt = self._hash_password(password)
            
            # Create user data
            user_data = {
                'username': username,
                'password_hash': hashed_password,
                'salt': salt,
                'email': email,
                'created_at': str(datetime.now())
            }
            
            # Save user data
            file_path = os.path.join(self.users_dir, f"{username}.json")
            with open(file_path, 'w') as f:
                json.dump(user_data, f, indent=4)
            
            return True
        except Exception as e:
            print(f"Error registering user: {str(e)}")
            return False
    
    def guest_login(self) -> str:
        """Login as a guest user with temporary username"""
        guest_id = secrets.token_hex(6)  # Generate a unique guest ID
        guest_username = f"guest_{guest_id}"
        return guest_username
    
    def verify_user(self, username: str, password: str) -> bool:
        """Verify user credentials"""
        try:
            user_data = self.get_user(username)
            if not user_data:
                return False
            
            # Hash provided password with stored salt
            hashed_password, _ = self._hash_password(password, user_data['salt'])
            
            # Compare hashed passwords
            return hashed_password == user_data['password_hash']
        except Exception as e:
            print(f"Error verifying user: {str(e)}")
            return False
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user data"""
        try:
            file_path = os.path.join(self.users_dir, f"{username}.json")
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error getting user: {str(e)}")
            return None
    
    def update_user(self, username: str, user_data: Dict) -> bool:
        """Update user data"""
        try:
            file_path = os.path.join(self.users_dir, f"{username}.json")
            if not os.path.exists(file_path):
                return False
            
            # Load existing data
            with open(file_path, 'r') as f:
                existing_data = json.load(f)
            
            # Update data
            existing_data.update(user_data)
            
            # Save updated data
            with open(file_path, 'w') as f:
                json.dump(existing_data, f, indent=4)
            
            return True
        except Exception as e:
            print(f"Error updating user: {str(e)}")
            return False 