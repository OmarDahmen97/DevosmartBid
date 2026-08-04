from bson import ObjectId
from app.embedding.embedding_chunker import (
    serialize_category_description_list,
    serialize_education_list,
    serialize_languages_list,
    serialize_certifications_list,
)

_candidate_cache: dict[tuple[str, int], dict] = {}


def clear_candidate_cache() -> None:
    _candidate_cache.clear()


def _get_candidate_version(mongo_collection, candidate_id: str, version_number: int) -> dict | None:
    key = (candidate_id, version_number)
    if key in _candidate_cache:
        return _candidate_cache[key]

    candidate = mongo_collection.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        _candidate_cache[key] = None
        return None

    version = next(
        (v for v in candidate["versions"] if v["version_number"] == version_number),
        None,
    )
    _candidate_cache[key] = version
    return version


LIST_SERIALIZERS = {
    "expertise_areas": serialize_category_description_list,
    "functional_skills": serialize_category_description_list,
    "education": serialize_education_list,
    "languages": serialize_languages_list,
    "certifications": serialize_certifications_list,
}


def resolve_chunk_to_mongo_source(mongo_collection, metadata: dict) -> dict:
    candidate_id = metadata["candidate_id"]
    version_number = metadata["version_number"]
    version = _get_candidate_version(mongo_collection, candidate_id, version_number)
    if version is None:
        return None

    structured = version["structured"]
    chunk_type = metadata["chunk_type"]

    if chunk_type == "experience":
        experiences = structured.get("experience", [])
        idx = metadata["experience_index"]
        return experiences[idx] if idx < len(experiences) else None

    if chunk_type == "project":
        projects = structured.get("projects", [])
        idx = metadata["project_index"]
        return projects[idx] if idx < len(projects) else None

    return structured.get(chunk_type)


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
    version_number = metadata["version_number"]
    version = _get_candidate_version(mongo_collection, candidate_id, version_number)
    if version is None:
        return []

    chunk_type = metadata["chunk_type"]
    list_serializer = LIST_SERIALIZERS.get(chunk_type)
    if not list_serializer:
        return []

    items = version["structured"].get(chunk_type, [])

    def serialize_one(item):
        return list_serializer([item])

    matched_indices = find_matching_mongo_items(chunk_text, items, serialize_one)
    return [items[i] for i in matched_indices]