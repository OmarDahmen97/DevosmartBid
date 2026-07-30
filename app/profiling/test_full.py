from app.profiling.profile_detector_full_cv import detect_profiles_full
from app.profiling.profile_detector_full_cv_local import detect_profiles_full_local
import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates = db["candidates"]

candidate = candidates.find_one({"normalized_name": "ahmed amine ben souayeh"})

result = detect_profiles_full(candidate)
#local
#result=detect_profiles_full_local(candidate)
from app.profiling.profile_builder import build_profiles_document, store_candidate_profiles
detection_result = detect_profiles_full(candidate)
profiles_doc = build_profiles_document(candidate, detection_result)
print(json.dumps(profiles_doc, indent=2, ensure_ascii=False))  # inspecte AVANT de stocker

store_candidate_profiles(db["candidate_profiles"], profiles_doc)