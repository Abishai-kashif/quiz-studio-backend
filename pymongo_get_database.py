from pymongo import MongoClient
import certifi
import time

def get_database(): 
   # Provide the mongodb atlas url to connect python to mongodb using pymongo
   CONNECTION_STRING = "mongodb+srv://abishai-kashif:rishta-DB-pass-1@cluster0.feufr8e.mongodb.net/"

   # Try local MongoDB first (faster)
   try:
       print("🔗 Trying local MongoDB...")
       local_client = MongoClient("mongodb://localhost:27017/", 
                                serverSelectionTimeoutMS=2000)  # 2 seconds timeout
       local_client.admin.command('ping')
       print("✅ Connected to local MongoDB!")
       return local_client['hackathon']
   except Exception as e:
       print(f"❌ Local MongoDB not available: {e}")
   
   # Try MongoDB Atlas as fallback
   try:
       print("🔗 Connecting to MongoDB Atlas...")
       client = MongoClient(
           CONNECTION_STRING, 
           tlsCAFile=certifi.where(),
           serverSelectionTimeoutMS=5000  # 5 seconds timeout
       )
       
       # Test the connection
       client.admin.command('ping')
       print("✅ Successfully connected to MongoDB Atlas!")
       
       # Create the database
       return client['hackathon']
       
   except Exception as e:
       print(f"❌ MongoDB Atlas connection failed: {e}")
       print("⚠️  Server will start without database connection")
       return None
  
# This is added so that many files can reuse the function get_database()
if __name__ == "__main__":   
  
   # Get the database
   dbname = get_database()