# app/generation/mongo_resolver.py

from bson import ObjectId
from app.embedding.embedding_chunker import (
    serialize_category_description_list,
    serialize_education_list,
    serialize_languages_list,
    serialize_certifications_list,
)

# Maps each list-type chunk_type to its list serializer.
# Each serializer is called with a single-element list ([item]) to get
# the exact same text representation as when the item was chunked,
# so it can be matched against a Chroma chunk's text.
LIST_SERIALIZERS = {
    "expertise_areas": serialize_category_description_list,
    "functional_skills": serialize_category_description_list,
    "education": serialize_education_list,
    "languages": serialize_languages_list,
    "certifications": serialize_certifications_list,
}


def resolve_chunk_to_mongo_source(mongo_collection, metadata: dict) -> dict:
    """Resolve experience/project/simple-field chunks back to their Mongo source. Unchanged."""
    candidate = mongo_collection.find_one({"_id": ObjectId(metadata["candidate_id"])})
    if not candidate:
        return None

    version = next(
        (v for v in candidate["versions"] if v["version_number"] == metadata["version_number"]),
        None,
    )
    if not version:
        return None

    structured = version["structured"]
    chunk_type = metadata["chunk_type"]

    if chunk_type == "experience":
        experiences = structured.get("experience", [])
        idx = metadata["experience_index"]
        return experiences[idx] if idx < len(experiences) else None

    elif chunk_type == "project":
        projects = structured.get("projects", [])
        idx = metadata["project_index"]
        return projects[idx] if idx < len(projects) else None

    else:
        return structured.get(chunk_type)


def find_matching_mongo_items(chunk_text: str, mongo_items: list[dict], serialize_one) -> list[int]:
    """
    Given a chunk of text (a token-window slice of the concatenated serialization)
    and the original Mongo items of the same section, find which item indices
    overlap (even partially, due to token-boundary truncation) with this chunk.
    Literal substring overlap, not semantic search — the chunk is a deterministic
    slice of the same serialized strings stored in Mongo.

    serialize_one(item) must return the same text an item would produce when
    serialized alone (e.g. serialize_category_description_list([item])).
    """
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
    """
    For list-type sections (expertise_areas, functional_skills, education,
    languages, certifications), resolve a Chroma chunk back to the exact
    Mongo items it overlaps with.
    """
    candidate = mongo_collection.find_one({"_id": ObjectId(metadata["candidate_id"])})
    if not candidate:
        return []

    version = next(
        (v for v in candidate["versions"] if v["version_number"] == metadata["version_number"]),
        None,
    )
    if not version:
        return []

    chunk_type = metadata["chunk_type"]
    list_serializer = LIST_SERIALIZERS.get(chunk_type)
    if not list_serializer:
        return []

    items = version["structured"].get(chunk_type, [])

    # wrap the list serializer so it works on one item at a time
    def serialize_one(item):
        return list_serializer([item])

    matched_indices = find_matching_mongo_items(chunk_text, items, serialize_one)
    return [items[i] for i in matched_indices]