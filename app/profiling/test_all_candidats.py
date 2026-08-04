"""
Batch-run profile detection across every candidate in the base, skipping
candidates already present in candidate_profiles (so re-running this script
after a crash or partial run doesn't re-call the LLM for candidates already done).
"""

import os
import time
from pymongo import MongoClient
from dotenv import load_dotenv

from app.profiling.profile_detector_full_cv import detect_profiles_full
from app.profiling.profile_builder import build_profiles_document, store_candidate_profiles

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client["cv_platform"]
candidates = db["candidates"]
candidate_profiles = db["candidate_profiles"]


def run_batch(force: bool = False, sleep_between_calls: float = 1.0) -> None:
    """
    force=False (default): skip candidates already present in candidate_profiles.
    force=True: re-run and overwrite everyone, even if already stored.
    """
    already_done = set()
    if not force:
        already_done = {
            doc["candidate_id"] for doc in candidate_profiles.find({}, {"candidate_id": 1})
        }
        print(f"{len(already_done)} candidat(s) déjà présents dans candidate_profiles — seront ignorés.")

    total = candidates.count_documents({})
    processed, skipped, failed = 0, 0, 0

    for candidate in candidates.find({}):
        candidate_id = str(candidate["_id"])
        name = candidate.get("name", "?")

        if candidate_id in already_done:
            skipped += 1
            continue

        if not candidate.get("versions"):
            print(f"[SKIP] {name} : aucune version, rien à traiter.")
            skipped += 1
            continue

        try:
            print(f"[{processed + skipped + failed + 1}/{total}] Détection profils : {name}...")
            detection_result = detect_profiles_full(candidate)
            profiles_doc = build_profiles_document(candidate, detection_result)
            store_candidate_profiles(candidate_profiles, profiles_doc)
            processed += 1
            print(f"  → {len(profiles_doc['profiles'])} profil(s) stocké(s).")
        except Exception as e:
            failed += 1
            print(f"  → ÉCHEC pour {name} ({candidate_id}) : {e}")

        time.sleep(sleep_between_calls)  

    print(f"\n{'#' * 60}")
    print(f"TERMINÉ : {processed} traités, {skipped} ignorés (déjà présents/sans version), {failed} échecs.")
    print(f"{'#' * 60}")


if __name__ == "__main__":
    run_batch(force=False)