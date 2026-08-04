"""
app/main_usage.py

Two usage modes:

1. CV + mission proposal  -> extract, store, semantic search, return matched CV JSON.
2. CV only                -> extract, store, detect + store distinct professional profiles.

Usage:
    python -m app.main_usage --cv path/to/cv.pdf --mission "mission text here"
    python -m app.main_usage --cv path/to/cv.pdf
"""

import argparse
import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv

from app.embedding.embedder import Embedder
from app.embedding.vector_store import VectorStore
from app.embedding.embedding_chunker import build_chunks_for_version
from app.generation.cv_json_builder import is_candidate_relevant_v2, build_matched_cv_json
from app.profiling.profile_detector_full_cv import detect_profiles_full
from app.profiling.profile_builder import build_profiles_document, store_candidate_profiles

from app.extraction.pipeline import extract_and_store_cv

load_dotenv()
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["cv_platform"]
candidates_collection = db["candidates"]
candidate_profiles_collection = db["candidate_profiles"]

# Lazy-loaded: the SBERT model (Embedder) and Chroma (VectorStore) are only
# needed for matching mode. Profile detection uses Gemini, not the local
# embedder or Chroma search -- loading SBERT eagerly at import time wasted a
# few seconds + memory on every profile-only run for nothing.
_embedder = None
_store = None


def get_embedder():
    global _embedder
    if _embedder is None:
        print("[chargement] SBERT (Embedder)...")
        _embedder = Embedder()
    return _embedder


def get_store():
    global _store
    if _store is None:
        print("[chargement] ChromaDB (VectorStore)...")
        _store = VectorStore()
    return _store


def index_candidate_version(candidate: dict, version: dict) -> None:
    """(Re)build and index Chroma chunks for one candidate version."""
    embedder = get_embedder()
    store = get_store()
    candidate_id = str(candidate["_id"])
    version_number = version["version_number"]
    print(f"[indexation] Suppression des anciens chunks (v{version_number})...")
    store.delete_candidate_chunks(candidate_id, version_number=version_number)
    print("[indexation] Découpage en chunks...")
    chunks = build_chunks_for_version(candidate, version, tokenizer=embedder.model.tokenizer)
    print(f"[indexation] Embedding de {len(chunks)} chunks...")
    enriched = embedder.embed_chunks(chunks)
    print("[indexation] Écriture dans ChromaDB...")
    store.index_chunks(enriched)
    print("[indexation] Terminé.")


def get_candidate(cv_path: str = None, normalized_name: str = None) -> dict:
    """
    Resolve the candidate document either by running the full extraction
    pipeline on a CV file, or by fetching an already-stored candidate
    directly from MongoDB (skips extraction entirely).
    """
    if normalized_name:
        print(f"[source] Lecture directe en base : normalized_name='{normalized_name}'")
        candidate = candidates_collection.find_one({"normalized_name": normalized_name})
        if candidate is None:
            raise ValueError(f"Aucun candidat trouvé avec normalized_name='{normalized_name}'")
        print(f"[source] Candidat trouvé : {candidate.get('name')} ({len(candidate.get('versions', []))} version(s))")
        return candidate

    return extract_and_store_cv(cv_path, candidates_collection=candidates_collection)


def run_matching_mode(cv_path: str = None, mission_text: str = None, normalized_name: str = None) -> dict:
    """Mode 1: CV + mission -> extract, store, semantic search, return matched CV JSON."""
    candidate = get_candidate(cv_path=cv_path, normalized_name=normalized_name)

    versions = candidate.get("versions", [])
    if not versions:
        return {}

    candidate_id = str(candidate["_id"])
    latest_version = versions[-1]

    for version in versions:
        index_candidate_version(candidate, version)

    query_vec = get_embedder().model.encode(mission_text).tolist()

    print("[matching] Évaluation de la pertinence sur toutes les versions...")
    is_relevant, avg_score = is_candidate_relevant_v2(
        store=get_store(),
        query_vec=query_vec,
        candidate_id=candidate_id,
        version_number=None,
    )
    print(f"[matching] Pertinent : {is_relevant} (score moyen: {avg_score}%)")

    if not is_relevant:
        return {}

    print("[matching] Construction du JSON final (toutes versions, dédoublonné)...")
    return build_matched_cv_json(
        get_store(), candidates_collection, candidate_id,
        latest_version["version_number"], query_vec,
        all_versions=True,
    )


def run_matching_all(mission_text: str) -> list[dict]:
    """
    Mode 3: mission only (no --cv, no --normalized-name) -> scan every stored
    candidate, index+match each against the mission, return the list of
    relevant ones with their matched CV JSON. No extraction happens here --
    only candidates already in MongoDB are considered.
    """
    print("[matching-all] Embedding de la mission...")
    query_vec = get_embedder().model.encode(mission_text).tolist()

    total = candidates_collection.count_documents({})
    relevant_results = []

    for i, candidate in enumerate(candidates_collection.find({}), start=1):
        name = candidate.get("name", "?")
        versions = candidate.get("versions", [])
        if not versions:
            print(f"[{i}/{total}] {name} : aucune version, ignoré.")
            continue

        candidate_id = str(candidate["_id"])
        latest_version = versions[-1]

        print(f"[{i}/{total}] {name} ({len(versions)} version(s))...")
        for version in versions:
            index_candidate_version(candidate, version)

        is_relevant, avg_score = is_candidate_relevant_v2(
            store=get_store(),
            query_vec=query_vec,
            candidate_id=candidate_id,
            version_number=None,
        )
        print(f"    -> pertinent : {is_relevant} (score moyen: {avg_score}%)")

        if not is_relevant:
            continue

        cv_json = build_matched_cv_json(
            get_store(), candidates_collection, candidate_id,
            latest_version["version_number"], query_vec,
            all_versions=True,
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
    """
    Scan every stored candidate against the mission text using
    is_candidate_relevant_v2. Returns only the names of candidates
    deemed relevant — no JSON generation, no Chroma indexing.
    """
    print("[matching] Embedding de la mission...")
    query_vec = get_embedder().model.encode(mission_text).tolist()

    total = candidates_collection.count_documents({})
    relevant_names = []

    for i, candidate in enumerate(candidates_collection.find({}), start=1):
        name = candidate.get("name", "?")
        versions = candidate.get("versions", [])
        if not versions:
            print(f"[{i}/{total}] {name} : aucune version, ignoré.")
            continue

        version = versions[-1]
        candidate_id = str(candidate["_id"])
        version_number = version["version_number"]

        print(f"[{i}/{total}] {name} (v{version_number})...")
        is_relevant, avg_score = is_candidate_relevant_v2(
            store=get_store(),
            query_vec=query_vec,
            candidate_id=candidate_id,
            version_number=version_number,
        )
        print(f"    -> pertinent : {is_relevant} (score moyen: {avg_score}%)")

        if is_relevant:
            relevant_names.append(name)

    print(f"\n{'#' * 60}")
    print(f"{len(relevant_names)} candidat(s) pertinent(s) sur {total}")
    print(f"{'#' * 60}")

    return relevant_names


def run_profile_mode(cv_path: str = None, normalized_name: str = None) -> dict:
    """
    Mode 2: CV only -> extract, store, detect professional profiles.
    No Chroma indexing here on purpose: profile detection runs entirely on
    the structured Mongo data via Gemini, it never touches the local
    embedder or the vector store.
    """
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
        results = run_matching_all(args.mission)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.mission:
        result = run_matching_mode(cv_path=args.cv, mission_text=args.mission, normalized_name=args.normalized_name)
        if not result:
            print("Candidat non pertinent pour cette mission.")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = run_profile_mode(cv_path=args.cv, normalized_name=args.normalized_name)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()