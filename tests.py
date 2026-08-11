# file: test_distinct_skills.py
"""
Récupère toutes les valeurs distinctes de skills directement depuis
MongoDB (merged_candidates), sans passer par l'API.

Usage:
    python test_distinct_skills.py
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
merged_candidates = db["merged_candidates"]


def main():
    values = merged_candidates.distinct("skills")
    values = sorted(v for v in values if v)

    print(f"{len(values)} valeur(s) distincte(s) pour 'skills' :\n")
    for v in values:
        print(f"  - {v}")


if __name__ == "__main__":
    main()