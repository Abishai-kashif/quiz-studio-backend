from pymongo import MongoClient
import certifi

def get_database(): 
   # Provide the mongodb atlas url to connect python to mongodb using pymongo
   CONNECTION_STRING = "mongodb+srv://abishai-kashif:rishta-DB-pass-1@cluster0.feufr8e.mongodb.net/"

   # Use system CA bundle to avoid SSL handshake failures on some platforms
   client = MongoClient(CONNECTION_STRING, tlsCAFile=certifi.where())

   # Create the database for our example (we will use the same database throughout the tutorial)
   return client['learnxaidb']
  
# This is added so that many files can reuse the function get_database()
if __name__ == "__main__":   
  
   # Get the database
   dbname = get_database()