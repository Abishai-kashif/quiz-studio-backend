#!/usr/bin/env python3
"""
Test script to verify signup functionality and MongoDB data saving
"""
import requests
import json
from pymongo_get_database import get_database

def test_signup():
    """Test the signup endpoint and verify data is saved to MongoDB"""
    
    # Test user data
    test_user = {
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "TestPassword123!"
    }
    
    print("🧪 Testing Signup Functionality")
    print("=" * 50)
    
    # 1. Test signup endpoint
    print(f"📝 Creating account for: {test_user['email']}")
    
    try:
        response = requests.post(
            "http://localhost:8001/signup",
            json=test_user,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📡 Response Status: {response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ Signup successful!")
            print(f"🔑 Access Token: {data.get('access_token', 'N/A')[:50]}...")
            print(f"🔒 Token Type: {data.get('token_type', 'N/A')}")
            
            # 2. Verify user exists in MongoDB
            print("\n🔍 Verifying user in MongoDB...")
            db = get_database()
            users_collection = db["users"]
            
            saved_user = users_collection.find_one({"email": test_user["email"]})
            
            if saved_user:
                print(f"✅ User found in MongoDB!")
                print(f"📧 Email: {saved_user.get('email')}")
                print(f"👤 Name: {saved_user.get('name')}")
                print(f"🆔 MongoDB ID: {saved_user.get('_id')}")
                print(f"📅 Created At: {saved_user.get('created_at')}")
                print(f"🔐 Password Hash: {saved_user.get('password', 'N/A')[:20]}...")
                
                # 3. Clean up - remove test user
                print(f"\n🧹 Cleaning up test user...")
                result = users_collection.delete_one({"email": test_user["email"]})
                if result.deleted_count > 0:
                    print(f"✅ Test user removed successfully")
                else:
                    print(f"⚠️ Failed to remove test user")
                    
            else:
                print(f"❌ User NOT found in MongoDB!")
                return False
                
        else:
            print(f"❌ Signup failed!")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to backend server at http://localhost:8001")
        print(f"💡 Make sure the backend server is running")
        return False
    except Exception as e:
        print(f"❌ Error during signup test: {e}")
        return False
    
    print("\n🎉 All tests passed! User data is being saved to MongoDB correctly.")
    return True

if __name__ == "__main__":
    test_signup()