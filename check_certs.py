import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client["cv_platform"]
doc = db["merged_candidates"].find_one({"certifications": {"$ne": []}})
print(doc.get("certifications") if doc else "Aucun candidat avec certifications non vides trouve")
