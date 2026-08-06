# file: app/embedding/mongo_resolver.py

from bson import ObjectId
from app.embedding.embedding_chunker import (
    serialize_category_description_list,
    serialize_education_list,
    serialize_languages_list,
    serialize_certifications_list,
)

"""
Resolves a chunk's metadata back to its source document in merged_candidates.
Each candidate now has a single consolidated document — the cache and lookups
are keyed on candidate_id alone, with no version dimension.
"""

_candidate_cache: dict[str, dict] = {}


def clear_candidate_cache() -> None:
    _candidate_cache.clear()


def _get_candidate(mongo_collection, candidate_id: str) -> dict | None:
    """
    Fetch the consolidated candidate document from merged_candidates.
    mongo_collection is expected to be scoped to merged_candidates, keyed by
    candidate_id (not _id) since that's the field build_merged_candidate_cv
    upserts on.
    """
    if candidate_id in _candidate_cache:
        return _candidate_cache[candidate_id]

    candidate = mongo_collection.find_one({"candidate_id": ObjectId(candidate_id)})
    _candidate_cache[candidate_id] = candidate
    return candidate


LIST_SERIALIZERS = {
    "expertise_areas": serialize_category_description_list,
    "functional_skills": serialize_category_description_list,
    "education": serialize_education_list,
    "languages": serialize_languages_list,
    "certifications": serialize_certifications_list,
}


def resolve_chunk_to_mongo_source(mongo_collection, metadata: dict) -> dict:
    candidate_id = metadata["candidate_id"]
    candidate = _get_candidate(mongo_collection, candidate_id)
    if candidate is None:
        return None

    chunk_type = metadata["chunk_type"]

    if chunk_type == "experience":
        experiences = candidate.get("experience", [])
        idx = metadata["experience_index"]
        return experiences[idx] if idx < len(experiences) else None

    if chunk_type == "project":
        projects = candidate.get("projects", [])
        idx = metadata["project_index"]
        return projects[idx] if idx < len(projects) else None

    return candidate.get(chunk_type)


def find_matching_mongo_items(chunk_text: str, mongo_items: list[dict], serialize_one) -> list[int]:
    matched_indices = []
    chunk_normalized = chunk_text.lower().strip()

    for idx, item in enumerate(mongo_items):
        item_text = serialize_one(item).lower().strip()
        if not item_text:
            continue

        if item_text in chunk_normalized:
            matched_indices.append(idx)
            continue

        item_words = item_text.split()
        if len(item_words) > 3:
            min_run = max(3, len(item_words) // 3)
            for start in range(len(item_words) - min_run + 1):
                run = " ".join(item_words[start:start + min_run])
                if run in chunk_normalized:
                    matched_indices.append(idx)
                    break

    return matched_indices


def resolve_list_section_matches(mongo_collection, metadata: dict, chunk_text: str) -> list[dict]:
    candidate_id = metadata["candidate_id"]
    candidate = _get_candidate(mongo_collection, candidate_id)
    if candidate is None:
        return []

    chunk_type = metadata["chunk_type"]
    list_serializer = LIST_SERIALIZERS.get(chunk_type)
    if not list_serializer:
        return []

    items = candidate.get(chunk_type, [])

    def serialize_one(item):
        return list_serializer([item])

    matched_indices = find_matching_mongo_items(chunk_text, items, serialize_one)
    return [items[i] for i in matched_indices]