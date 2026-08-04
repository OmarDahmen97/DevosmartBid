from app.embedding.embedding_chunker import serialize_experience_to_text
from app.generation.mongo_resolver import (
    resolve_chunk_to_mongo_source,
    resolve_list_section_matches,
)

from app.config import (
    MIN_RELEVANCE_SCORE,
    PASS_A_SECTION_THRESHOLDS,
    SEARCH_CONFIG,
    EXPERIENCE_SEARCH_CONFIG,
    PROJECT_SEARCH_CONFIG,
    INDEXED_TYPES,
    LIST_TYPES,
)
from bson import ObjectId
from rapidfuzz import fuzz


def serialize_project_to_text(project: dict) -> str:
    name = project.get("name")
    description = project.get("description")
    technologies = project.get("technologies") or []

    parts = [name] if name else []
    if description:
        parts.append(description)
    tech_text = ", ".join(technologies)
    if tech_text:
        parts.append(f"Technologies: {tech_text}")

    return ". ".join(parts)


def deduplicate_items(items: list[dict], serialize_fn, threshold: float = 90.0) -> list[dict]:
    seen_texts = []
    result = []
    for item in items:
        text = serialize_fn(item).lower().strip()
        if not text:
            continue
        is_dup = False
        for seen in seen_texts:
            if fuzz.ratio(text, seen) >= threshold:
                is_dup = True
                break
        if not is_dup:
            seen_texts.append(text)
            result.append(item)
    return result


def distance_to_score(distance: float) -> float:
    """Convert a cosine distance into a 0-100% similarity score."""
    similarity = 1 - distance
    return round(max(0, similarity) * 100, 1)


def is_candidate_relevant_v2(
    store,
    query_vec,
    candidate_id,
    version_number,
    min_score: float = MIN_RELEVANCE_SCORE,
    section_thresholds: dict = None,
):
    critical_sections = ["summary", "experience", "project"]  # skills/expertise_areas retirés

    if section_thresholds is None:
        section_thresholds = PASS_A_SECTION_THRESHOLDS

    best_scores = []
    for section in critical_sections:
        threshold = section_thresholds.get(section, 0.8)
        res = store.search_section(
            query_vec, chunk_types=section, candidate_id=candidate_id,
            version_number=version_number, distance_threshold=threshold,
            min_results=0, max_results=3,
        )
        if res:
            best_scores.append(max(distance_to_score(r["distance"]) for r in res))
        # sinon : section vide, non ajoutée -> ne tire pas la moyenne vers le bas

    if not best_scores:
        return False, 0.0

    sections_above = sum(1 for s in best_scores if s >= min_score)
    avg_score = sum(best_scores) / len(best_scores)
    return sections_above >= 1 and avg_score >= (min_score * 0.5), avg_score


def build_matched_cv_json(store, mongo_collection, candidate_id: str, version_number: int, query_vec: list[float], all_versions: bool = False) -> dict:
    """
    Static sections (summary, skills, education, etc.) are included wholesale
    from Mongo — no semantic filtering. Only experience/project go through
    Chroma search, since that's the only part of a CV that should adapt to
    the target mission.

    NOTE: no relevance gate here on purpose. This function is called both for
    single-CV-upload flows (user wants a JSON regardless of match quality) and
    for batch scans across the whole candidate base (where the caller applies
    is_candidate_relevant_v2 itself beforehand and skips irrelevant candidates).
    Keeping the gate out of this function keeps both use cases correct without
    a mode flag.
    """
    candidate = mongo_collection.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        return {}

    if all_versions:
        versions = candidate.get("versions", [])
        version = versions[-1] if versions else None
    else:
        version = next((v for v in candidate["versions"] if v["version_number"] == version_number), None)
    if not version:
        return {}

    structured = version["structured"]
    result = {}

    STATIC_SECTIONS = [
        "summary", "skills", "expertise_areas", "functional_skills",
        "education", "languages", "certifications",
        "countries_worked", "professional_affiliations",
    ]
    for section in STATIC_SECTIONS:
        value = structured.get(section)
        if value:
            result[section] = value

    search_version_number = None if all_versions else version_number

    # experience + project : recherches séparées, thresholds différents
    experience_res = store.search_section(
        query_vec, chunk_types="experience", candidate_id=candidate_id,
        version_number=search_version_number, **EXPERIENCE_SEARCH_CONFIG
    )
    project_res = store.search_section(
        query_vec, chunk_types="project", candidate_id=candidate_id,
        version_number=search_version_number, **PROJECT_SEARCH_CONFIG
    )

    experiences, projects = [], []
    seen_experience_indices, seen_project_indices = set(), set()

    for r in experience_res:
        metadata = r["metadata"]
        idx = metadata["experience_index"]
        if idx in seen_experience_indices:
            continue
        seen_experience_indices.add(idx)
        item = resolve_chunk_to_mongo_source(mongo_collection, metadata)
        if item:
            experiences.append(item)

    for r in project_res:
        metadata = r["metadata"]
        idx = metadata["project_index"]
        if idx in seen_project_indices:
            continue
        seen_project_indices.add(idx)
        item = resolve_chunk_to_mongo_source(mongo_collection, metadata)
        if item:
            projects.append(item)

    if all_versions:
        experiences = deduplicate_items(experiences, serialize_experience_to_text)
        projects = deduplicate_items(projects, serialize_project_to_text)

    if experiences:
        result["experience"] = experiences
    if projects:
        result["projects"] = projects

    return result