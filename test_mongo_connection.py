#!/usr/bin/env python3
"""
MongoDB Connection Test Script
Tests the MongoDB connection and provides fallback options
"""

import os
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

load_dotenv()

def test_mongodb_connection():
    """Test MongoDB Atlas connection"""
    try:
        print("🔍 Testing MongoDB Atlas connection...")
        
        # Try the hardcoded connection string first
        CONNECTION_STRING = "mongodb+srv://abishai-kashif:rishta-DB-pass-1@cluster0.feufr8e.mongodb.net/"
        
        print(f"📡 Attempting to connect to: {CONNECTION_STRING[:50]}...")
        
        # Set a shorter timeout for testing
        client = MongoClient(
            CONNECTION_STRING, 
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000  # 5 second timeout
        )
        
        # Test the connection
        client.admin.command('ping')
        print("✅ MongoDB Atlas connection successful!")
        
        # Test database access
        db = client['learnxaidb']
        collections = db.list_collection_names()
        print(f"📊 Available collections: {collections}")
        
        return True, client
        
    except Exception as e:
        print(f"❌ MongoDB Atlas connection failed: {str(e)}")
        return False, None

def setup_local_fallback():
    """Setup local MongoDB fallback"""
    try:
        print("🔄 Attempting local MongoDB fallback...")
        
        # Try local MongoDB
        local_client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000)
        local_client.admin.command('ping')
        
        print("✅ Local MongoDB connection successful!")
        return True, local_client
        
    except Exception as e:
        print(f"❌ Local MongoDB also failed: {str(e)}")
        return False, None

def create_mock_database():
    """Create a mock database for development"""
    print("🔧 Setting up mock database for development...")
    
    # Create a simple in-memory mock
    mock_db = {
        "users": [],
        "sessions": [],
        "quizzes": []
    }
    
    print("✅ Mock database created for development!")
    return mock_db

if __name__ == "__main__":
    print("🚀 MongoDB Connection Diagnostics")
    print("=" * 50)
    
    # Test Atlas connection
    atlas_success, atlas_client = test_mongodb_connection()
    
    if not atlas_success:
        print("\n🔄 Trying fallback options...")
        
        # Try local MongoDB
        local_success, local_client = setup_local_fallback()
        
        if not local_success:
            print("\n⚠️  No MongoDB available - using mock database")
            mock_db = create_mock_database()
            print("💡 Suggestion: Install local MongoDB or fix Atlas connection")
        else:
            print("✅ Using local MongoDB as fallback")
    else:
        print("✅ Using MongoDB Atlas")
    
    print("\n" + "=" * 50)
    print("🏁 Diagnostics complete!")