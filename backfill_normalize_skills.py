# file: backfill_normalize_skills.py
"""
Applies the current casing normalization + MANUAL_ALIASES (see
app/normalize_sections/normalize_skills.py) to skills already stored in
candidatesV2 and merged_candidates.

Note: casing normalization here runs across each version's/document's own
skills list independently (same rule the pipeline applies per-CV), not
across the whole database -- consistent with how normalize_skill_list works
at extraction time. Re-run this after adding new entries to MANUAL_ALIASES
to propagate them to existing data.

Usage:
    python backfill_normalize_skills.py
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

from app.normalize_sections.normalize_skills import normalize_skill_list

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates_collection = db["candidatesV2"]
merged_candidates_collection = db["merged_candidates"]


def backfill_candidates_v2() -> int:
    updated = 0
    cursor = candidates_collection.find({"versions.structured.skills": {"$exists": True}})

    for candidate in cursor:
        versions = candidate.get("versions", [])
        changed = False

        for version in versions:
            structured = version.get("structured", {})
            raw_skills = structured.get("skills")
            if not raw_skills:
                continue
            normalized = normalize_skill_list(raw_skills)
            if normalized != raw_skills:
                structured["skills"] = normalized
                changed = True

        if changed:
            candidates_collection.update_one(
                {"_id": candidate["_id"]}, {"$set": {"versions": versions}}
            )
            updated += 1

    return updated


def backfill_merged_candidates() -> int:
    updated = 0
    cursor = merged_candidates_collection.find({"skills": {"$exists": True}})

    for doc in cursor:
        raw_skills = doc.get("skills")
        if not raw_skills:
            continue
        normalized = normalize_skill_list(raw_skills)
        if normalized != raw_skills:
            merged_candidates_collection.update_one(
                {"_id": doc["_id"]}, {"$set": {"skills": normalized}}
            )
            updated += 1

    return updated


def main():
    print("[1/2] Normalizing candidatesV2...")
    v2_count = backfill_candidates_v2()
    print(f"      -> {v2_count} candidate(s) updated")

    print("[2/2] Normalizing merged_candidates...")
    merged_count = backfill_merged_candidates()
    print(f"      -> {merged_count} candidate(s) updated")


if __name__ == "__main__":
    main()