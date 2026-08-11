# file: app/main_usage.py
"""
app/main_usage.py

Two usage modes:

1. CV + mission proposal  -> extract, store, merge, semantic search, adapt experiences via LLM, return matched CV JSON.
2. CV only                -> extract, store, detect + store distinct professional profiles.

Extraction and storage still happen against candidatesV2 (the raw,
per-version source of truth). Indexing and semantic matching now operate on
merged_candidates: each candidate has a single consolidated, deduplicated
view (built by app.merging.experience_similarity.build_merged_candidate_cv),
so there is no more per-version indexing loop and no version_number anywhere
in the matching path.

Usage:
    python -m app.main_usage --cv path/to/cv.pdf --mission "mission text here" --language "French"
    python -m app.main_usage --cv path/to/cv.pdf
"""

import argparse
import json
import os
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

from app.embedding.embedder import get_shared_embedder
from app.embedding.vector_store import VectorStore
from app.embedding.embedding_chunker import build_chunks_for_candidate
from app.generation.cv_json_builder import is_candidate_relevant_v2, build_matched_cv_json
from app.generation.mongo_resolver import invalidate_candidate_cache
from app.merging.experience_similarity import build_merged_candidate_cv
from app.profiling.profile_detector_full_cv import detect_profiles_full
from app.profiling.profile_builder import build_profiles_document, store_candidate_profiles

from app.extraction.pipeline import extract_and_store_cv

load_dotenv()
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["cv_platform"]
candidates_collection = db["candidatesV2"]
merged_candidates_collection = db["merged_candidates"]
candidate_profiles_collection = db["candidate_profiles"]

_store = None


def get_embedder():
    """Delegates to the process-wide shared singleton (app.embedding.embedder)."""
    return get_shared_embedder()


def get_store():
    global _store
    if _store is None:
        print("[chargement] ChromaDB (VectorStore)...")
        _store = VectorStore()
    return _store


def sync_merged_candidate(candidate_id: str) -> dict:
    print("[merge] Fusion et dédoublonnage des expériences...")
    merged = build_merged_candidate_cv(
        mongo_collection=candidates_collection,
        candidate_id=candidate_id,
        target_collection=merged_candidates_collection,
    )
    if merged:
        print(f"[merge] {len(merged.get('experience', []))} expérience(s) unique(s) après fusion.")
    return merged


def index_merged_candidate(merged_candidate: dict) -> None:
    embedder = get_embedder()
    store = get_store()
    candidate_id = str(merged_candidate.get("candidate_id") or merged_candidate["_id"])
    print("[indexation] Suppression des anciens chunks...")
    store.delete_candidate_chunks(candidate_id)
    print("[indexation] Découpage en chunks...")
    chunks = build_chunks_for_candidate(merged_candidate, tokenizer=embedder.model.tokenizer)
    print(f"[indexation] Embedding de {len(chunks)} chunks...")
    enriched = embedder.embed_chunks(chunks)
    print("[indexation] Écriture dans ChromaDB...")
    store.index_chunks(enriched)
    print("[indexation] Terminé.")


def get_candidate(cv_path: str = None, normalized_name: str = None) -> dict:
    if normalized_name:
        print(f"[source] Lecture directe en base : normalized_name='{normalized_name}'")
        candidate = candidates_collection.find_one({"normalized_name": normalized_name})
        if candidate is None:
            raise ValueError(f"Aucun candidat trouvé avec normalized_name='{normalized_name}'")
        print(f"[source] Candidat trouvé : {candidate.get('name')} ({len(candidate.get('versions', []))} version(s))")
        return candidate

    return extract_and_store_cv(cv_path, candidates_collection=candidates_collection)


def find_candidate_id_by_name(name: str) -> str | None:
    candidate = candidates_collection.find_one({
        "$or": [
            {"name": {"$regex": f"^{name}$", "$options": "i"}},
            {"versions.structured.name": {"$regex": f"^{name}$", "$options": "i"}},
        ]
    })
    return str(candidate["_id"]) if candidate else None


def run_matching_for_candidate_id(
    candidate_id: str, mission_text: str, target_language: str = "French"
) -> dict:
    merged = sync_merged_candidate(candidate_id)
    if not merged:
        return {}

    index_merged_candidate(merged)

    query_vec = get_embedder().model.encode(mission_text).tolist()

    print("[matching] Évaluation de la pertinence...")
    is_relevant, avg_score = is_candidate_relevant_v2(
        store=get_store(),
        query_vec=query_vec,
        candidate_id=candidate_id,
    )
    print(f"[matching] Pertinent : {is_relevant} (score moyen: {avg_score}%)")

    if not is_relevant:
        return {"is_relevant": False, "avg_score": avg_score, "cv_json": {}}

    print("[matching] Construction et adaptation du JSON final...")
    cv_json = build_matched_cv_json(
        get_store(),
        merged_candidates_collection,
        candidate_id,
        query_vec,
        mission_text=mission_text,
        target_language=target_language,
    )
    return {"is_relevant": True, "avg_score": avg_score, "cv_json": cv_json}


def run_matching_mode(
    cv_path: str = None,
    mission_text: str = None,
    normalized_name: str = None,
    target_language: str = "French",
) -> dict:
    candidate = get_candidate(cv_path=cv_path, normalized_name=normalized_name)
    candidate_id = str(candidate["_id"])

    merged = sync_merged_candidate(candidate_id)
    if not merged:
        return {}

    index_merged_candidate(merged)

    query_vec = get_embedder().model.encode(mission_text).tolist()

    print("[matching] Évaluation de la pertinence...")
    is_relevant, avg_score = is_candidate_relevant_v2(
        store=get_store(),
        query_vec=query_vec,
        candidate_id=candidate_id,
    )
    print(f"[matching] Pertinent : {is_relevant} (score moyen: {avg_score}%)")

    if not is_relevant:
        return {}

    print("[matching] Construction et adaptation du JSON final...")
    return build_matched_cv_json(
        get_store(),
        merged_candidates_collection,
        candidate_id,
        query_vec,
        mission_text=mission_text,
        target_language=target_language,
    )


def run_matching_all(mission_text: str, target_language: str = "French") -> list[dict]:
    print("[matching-all] Embedding de la mission...")
    query_vec = get_embedder().model.encode(mission_text).tolist()

    total = candidates_collection.count_documents({})
    relevant_results = []

    for i, candidate in enumerate(candidates_collection.find({}), start=1):
        name = candidate.get("name", "?")
        candidate_id = str(candidate["_id"])

        print(f"[{i}/{total}] {name}...")
        merged = sync_merged_candidate(candidate_id)
        if not merged:
            print("    -> aucune version exploitable, ignoré.")
            continue

        index_merged_candidate(merged)

        is_relevant, avg_score = is_candidate_relevant_v2(
            store=get_store(),
            query_vec=query_vec,
            candidate_id=candidate_id,
        )
        print(f"    -> pertinent : {is_relevant} (score moyen: {avg_score}%)")

        if not is_relevant:
            continue

        cv_json = build_matched_cv_json(
            get_store(),
            merged_candidates_collection,
            candidate_id,
            query_vec,
            mission_text=mission_text,
            target_language=target_language,
        )
        relevant_results.append({
            "candidate_id": candidate_id,
            "candidate_name": name,
            "avg_score": avg_score,
            "cv_json": cv_json,
        })

    print(f"\n{'#' * 60}")
    print(f"TOTAL : {len(relevant_results)} candidat(s) pertinent(s) sur {total}")
    print(f"{'#' * 60}")

    return relevant_results


def get_relevant_candidate_names(mission_text: str) -> list[str]:
    print("[matching] Embedding de la mission...")
    query_vec = get_embedder().model.encode(mission_text).tolist()

    total = candidates_collection.count_documents({})
    relevant_names = []

    for i, candidate in enumerate(candidates_collection.find({}), start=1):
        name = candidate.get("name", "?")
        candidate_id = str(candidate["_id"])

        print(f"[{i}/{total}] {name}...")
        merged = sync_merged_candidate(candidate_id)
        if not merged:
            print("    -> aucune version exploitable, ignoré.")
            continue

        index_merged_candidate(merged)

        is_relevant, avg_score = is_candidate_relevant_v2(
            store=get_store(),
            query_vec=query_vec,
            candidate_id=candidate_id,
        )
        print(f"    -> pertinent : {is_relevant} (score moyen: {avg_score}%)")

        if is_relevant:
            relevant_names.append(name)

    print(f"\n{'#' * 60}")
    print(f"{len(relevant_names)} candidat(s) pertinent(s) sur {total}")
    print(f"{'#' * 60}")

    return relevant_names


FLAT_LIST_FIELDS = ["skills", "countries_worked", "professional_affiliations"]


def run_mission_matching(mission_text: str) -> list[dict]:
    print("[matching] Embedding de la mission...")
    query_vec = get_embedder().model.encode(mission_text).tolist()

    total = candidates_collection.count_documents({})
    relevant = []

    for i, candidate in enumerate(candidates_collection.find({}), start=1):
        name = candidate.get("name", "?")
        candidate_id = str(candidate["_id"])

        print(f"[{i}/{total}] {name}...")
        merged = sync_merged_candidate(candidate_id)
        if not merged:
            print("    -> aucune version exploitable, ignoré.")
            continue

        index_merged_candidate(merged)

        is_relevant, avg_score = is_candidate_relevant_v2(
            store=get_store(),
            query_vec=query_vec,
            candidate_id=candidate_id,
        )
        print(f"    -> pertinent : {is_relevant} (score moyen: {avg_score}%)")

        if is_relevant:
            relevant.append({
                "candidate_id": candidate_id,
                "name": name,
                "email": candidate.get("email"),
                "avg_score": avg_score,
            })

    relevant.sort(key=lambda c: c["avg_score"], reverse=True)

    print(f"\n{'#' * 60}")
    print(f"{len(relevant)} candidat(s) pertinent(s) sur {total}")
    print(f"{'#' * 60}")

    return relevant


def get_candidate_detail(candidate_id: str) -> dict:
    candidate = merged_candidates_collection.find_one({"candidate_id": ObjectId(candidate_id)})
    if not candidate:
        return {}
    candidate["_id"] = str(candidate["_id"])
    candidate["candidate_id"] = str(candidate["candidate_id"])
    return candidate


def get_distinct_section_values(section: str) -> list[str]:
    if section not in FLAT_LIST_FIELDS:
        raise ValueError(f"section must be one of {FLAT_LIST_FIELDS}, got '{section}'")
    values = merged_candidates_collection.distinct(section)
    return sorted(v for v in values if v)


def search_candidates(name: str = None, section: str = None, values: list[str] = None) -> list[dict]:
    query = {}
    if name:
        query["name"] = {"$regex": name, "$options": "i"}
    if section and values:
        if section not in FLAT_LIST_FIELDS:
            raise ValueError(f"section must be one of {FLAT_LIST_FIELDS}, got '{section}'")
        query[section] = {"$in": values}

    cursor = merged_candidates_collection.find(
        query, {"name": 1, "email": 1, "candidate_id": 1}
    )
    return [
        {
            "candidate_id": str(c.get("candidate_id") or c["_id"]),
            "name": c.get("name"),
            "email": c.get("email"),
        }
        for c in cursor
    ]


def delete_candidate(candidate_id: str) -> dict:
    candidates_result = candidates_collection.delete_one({"_id": ObjectId(candidate_id)})
    merged_result = merged_candidates_collection.delete_one({"candidate_id": ObjectId(candidate_id)})
    get_store().delete_candidate_chunks(candidate_id)
    invalidate_candidate_cache(candidate_id)

    return {
        "candidate_id": candidate_id,
        "deleted_from_candidatesV2": candidates_result.deleted_count > 0,
        "deleted_from_merged_candidates": merged_result.deleted_count > 0,
    }


def generate_cv_from_selection(payload: dict) -> dict:
    return {
        "status": "not_implemented",
        "message": "La génération de CV à partir de templates n'est pas encore disponible.",
        "received": payload,
    }


def run_profile_mode(cv_path: str = None, normalized_name: str = None) -> dict:
    candidate = get_candidate(cv_path=cv_path, normalized_name=normalized_name)

    print("[profils] Détection des profils (Gemini)...")
    detection_result = detect_profiles_full(candidate)
    print(f"[profils] {len(detection_result.get('profiles', []))} profil(s) détecté(s)")

    print("[profils] Construction du document profils...")
    profiles_doc = build_profiles_document(candidate, detection_result)

    print("[profils] Stockage dans candidate_profiles...")
    store_candidate_profiles(candidate_profiles_collection, profiles_doc)
    print("[profils] Terminé.")

    return profiles_doc


def main():
    parser = argparse.ArgumentParser(description="CV extraction + matching / profile detection")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--cv", help="Path to the CV file (pdf/docx/pptx) -- runs full extraction")
    source_group.add_argument(
        "--normalized-name",
        help="normalized_name of an already-stored candidate -- skips extraction, reads directly from MongoDB",
    )
    source_group.add_argument(
        "--all",
        action="store_true",
        help="Scan every stored candidate against --mission, return the list of relevant ones with their matched CV JSON (requires --mission)",
    )
    source_group.add_argument(
        "--names",
        action="store_true",
        help="Scan every stored candidate against --mission, return only the names of relevant candidates (requires --mission)",
    )
    parser.add_argument("--mission", required=False, help="Mission text. If omitted (and not --all/--names), runs profile detection instead.")
    parser.add_argument("--language", default="French", help="Language for experience adaptation (default: French)")
    args = parser.parse_args()

    if args.names:
        if not args.mission:
            parser.error("--names requires --mission")
        names = get_relevant_candidate_names(args.mission)
        for name in names:
            print(name)
        return

    if args.all:
        if not args.mission:
            parser.error("--all requires --mission")
        results = run_matching_all(args.mission, target_language=args.language)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.mission:
        result = run_matching_mode(
            cv_path=args.cv,
            mission_text=args.mission,
            normalized_name=args.normalized_name,
            target_language=args.language,
        )
        if not result:
            print("Candidat non pertinent pour cette mission.")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = run_profile_mode(cv_path=args.cv, normalized_name=args.normalized_name)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()