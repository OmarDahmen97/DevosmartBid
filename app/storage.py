from pymongo import MongoClient
from datetime import datetime
import os
from pymongo import MongoClient
from dotenv import load_application_environment, load_dotenv
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates = db["candidates"]

def get_dedup_key(cv_schema) -> tuple[str, str]:
    if cv_schema.email and cv_schema.email.strip():
        return ("email", cv_schema.email)
    return ("normalized_name", cv_schema.name.lower().strip())

def find_existing_by_raw_text(raw_text: str):
    """Cherche si ce texte brut exact existe déjà, tous candidats confondus."""
    doc = candidates.find_one({"versions.raw_text": raw_text})
    if doc:
        for v in doc["versions"]:
            if v["raw_text"] == raw_text:
                return v["version_number"]
    return None

def save_cv(cv_schema, raw_text: str):
    field, value = get_dedup_key(cv_schema)
    existing = candidates.find_one({field: value})

    if existing:
        for v in existing["versions"]:
            if v["raw_text"] == raw_text:
                return {"status": "duplicate", "email": cv_schema.email, "version": v["version_number"]}

    version_doc = {
        "version_number": (existing["versions"][-1]["version_number"] + 1) if existing else 1,
        "structured": cv_schema.model_dump(),
        "raw_text": raw_text,
        "uploaded_at": datetime.now().isoformat(),
    }

    if existing:
        candidates.update_one({field: value}, {"$push": {"versions": version_doc}})
    else:
        candidates.insert_one({
            "email": cv_schema.email,
            "name": cv_schema.name,
            "normalized_name": cv_schema.name.lower().strip(),
            "versions": [version_doc],
        })

    return {"status": "new_version" if existing else "new_candidate", "email": cv_schema.email, "version": version_doc["version_number"], "name": cv_schema.name}