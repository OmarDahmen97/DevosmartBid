import json
import os
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

from app.merging.experience_similarity import build_merged_candidate_cv

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]

# Collections MongoDB Atlas
candidates = db["candidatesV2"]
merged_candidates_col = db["merged_candidates"]  # Nueva collection de destination


def test_merge_by_candidate_name(candidate_name: str, threshold: float = 0.82):
    print(" Connexion a MongoDB Atlas...")

    # 1. Recherche du candidat
    print(f" Recherche du candidat : '{candidate_name}'...")
    candidate = candidates.find_one({
        "$or": [
            {"name": {"$regex": f"^{candidate_name}$", "$options": "i"}},
            {"versions.structured.name": {"$regex": f"^{candidate_name}$", "$options": "i"}}
        ]
    })

    if not candidate:
        print(f" Aucun candidat trouve avec le nom : {candidate_name}")
        return

    candidate_id = str(candidate["_id"])
    nb_versions = len(candidate.get("versions", []))
    print(f" Candidat trouve ! ID: {candidate_id}")
    print(f" Nombre de versions de CV : {nb_versions}")

    # 2. Exécution et Sauvegarde dans 'merged_candidates'
    print(f"\n Fusion et enregistrement dans 'merged_candidates'...")
    merged_cv = build_merged_candidate_cv(
        mongo_collection=candidates,
        candidate_id=candidate_id,
        target_collection=merged_candidates_col,  # Collection Atlas cible
        threshold=threshold
    )

    merged_experiences = merged_cv.get("experience", [])
    print("\n--- Resultat du CV Fusionne ---")
    print(f" Nom : {merged_cv.get('name')}")
    print(f" Nombre total d'experiences uniques : {len(merged_experiences)}")
    print(f" Sauvegarde effectuee dans MongoDB Atlas -> DB: cv_platform | Collection: merged_candidates")


if __name__ == "__main__":
    CANDIDATE_NAME_TO_TEST = "Sabria Jeribi"
    test_merge_by_candidate_name(CANDIDATE_NAME_TO_TEST, threshold=0.7)