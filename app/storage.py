from pymongo import MongoClient
from datetime import datetime
import os
from pymongo import MongoClient
from dotenv import  load_dotenv
from rapidfuzz import fuzz
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates = db["candidates"]

def get_dedup_key(cv_schema) -> tuple[str, str]:
    """if cv_schema.email and cv_schema.email.strip():
        return ("email", cv_schema.email)"""
    return ("normalized_name", cv_schema.name.lower().strip())

def find_existing_by_raw_text(raw_text: str):
    """Cherche si ce texte brut exact existe déjà, tous candidats confondus."""
    doc = candidates.find_one({"versions.raw_text": raw_text})
    if doc:
        for v in doc["versions"]:
            if v["raw_text"] == raw_text:
                return v["version_number"]
    return None

def save_cv(cv_schema, Eng_raw_text: str,original_raw_text: str = None):
    raw_text=Eng_raw_text
    field, value = get_dedup_key(cv_schema)
    existing = None
    
    # 1. Recherche par clé exacte (email ou nom normalisé exact)
    if value:
        existing = candidates.find_one({field: value})
        
    # 2. Recherche par similarité de nom si non trouvé
    if not existing and cv_schema.name:
        current_name_normalized = cv_schema.name.lower().strip()
        first_letter = current_name_normalized[0] if current_name_normalized else ""

        # Inversion prénom/nom
        parts = current_name_normalized.split()
        reversed_name = " ".join(reversed(parts)) if len(parts) > 1 else current_name_normalized

        potential_candidates = candidates.find({
            "normalized_name": {"$regex": f"^{first_letter}"}
        })

        for candidate in potential_candidates:
            existing_name = candidate.get("normalized_name", "")

            score_normal = fuzz.ratio(current_name_normalized, existing_name)
            score_reversed = fuzz.ratio(reversed_name, existing_name)

            if max(score_normal, score_reversed) >= 95:
                existing = candidate
                break

    # 3. Vérification des doublons de texte brut
    if existing:
        for v in existing["versions"]:
            if v["raw_text"] == raw_text:
                return {
                    "status": "duplicate", 
                    "email": cv_schema.email, 
                    "version": v["version_number"]
                }

    # 4. Création de la version
    if  original_raw_text:
        raw_text=original_raw_text
    version_number = (existing["versions"][-1]["version_number"] + 1) if existing else 1
    version_doc = {
        "version_number": version_number,
        "structured": cv_schema.model_dump(),
        "raw_text": raw_text,
        "uploaded_at": datetime.now().isoformat(),
    }

    # 5. ÉCRITURE DANS MONGODB 
    if existing:
        
        candidates.update_one(
            {"_id": existing["_id"]}, 
            {"$push": {"versions": version_doc}}
        )
    else:
        candidates.insert_one({
            "email": cv_schema.email,
            "name": cv_schema.name,
            "normalized_name": cv_schema.name.lower().strip(),
            "versions": [version_doc],
        })

    return {
        "status": "new_version" if existing else "new_candidate", 
        "email": cv_schema.email, 
        "version": version_doc["version_number"], 
        "name": cv_schema.name
    }