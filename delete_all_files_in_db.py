from pymongo import MongoClient
from config import MONGO_URI

# Connect to MongoDB
mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]

result = files_col.delete_many({})

print(f"Deleted {result.deleted_count} file documents from the database.")