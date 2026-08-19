import os
from pymongo import MongoClient
from dotenv import load_dotenv
from app.services.candidate_service import CandidateService

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client["cv_platform"]
service = CandidateService(db["merged_candidates"])
print(service.get_distinct_certifications())
