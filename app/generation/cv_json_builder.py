# file: app/generation/cv_json_builder.py

from app.embedding.embedding_chunker import serialize_experience_to_text
from app.generation.mongo_resolver import (
    resolve_chunk_to_mongo_source,
    resolve_list_section_matches,
)

from rapidfuzz import fuzz
from bson import ObjectId


from app.config import (
    MIN_RELEVANCE_SCORE,
    PASS_A_SECTION_THRESHOLDS,
    SECTION_RICHNESS_THRESHOLD,
)


def distance_to_score(distance: float) -> float:
    """Convert a cosine distance into a 0-100% similarity score."""
    similarity = 1 - distance
    return round(max(0, similarity) * 100, 1)


def compute_list_section_richness(section, items):
    """Richness for list sections."""
    if not items:
        return 0.0
    num_elements = len(items)
    if section in ("expertise_areas", "functional_skills"):
        lengths = [
            len((e.get("category") or "")) + len((e.get("description") or ""))
            for e in items
        ]
    elif section == "skills":
        lengths = [len(str(s)) for s in items]
    else:
        lengths = [len(str(item)) for item in items]
    avg_element_length = sum(lengths) / num_elements
    return avg_element_length * num_elements


def select_search_sections(structured, sections=None):
    sections = sections or [
        "summary", "skills", "expertise_areas", "functional_skills",
        "education", "languages", "certifications",
        "countries_worked", "professional_affiliations",
    ]
    selected = []
    for section in sections:
        value = structured.get(section)
        if not value:
            continue
        if section in ("expertise_areas", "functional_skills", "skills"):
            richness = compute_list_section_richness(section, value)
            if richness <= SECTION_RICHNESS_THRESHOLD:
                continue
        selected.append(section)
    return selected


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
    """
    Fuzzy near-duplicate filter, kept as a general-purpose utility. No longer
    invoked from build_matched_cv_json for experience/project — deduplication
    across CV versions is now handled upstream at merge time (merged_candidates
    already holds a single deduplicated experience list per candidate).
    """
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


def is_candidate_relevant_v2(
    store,
    query_vec,
    candidate_id,
    min_score: float = MIN_RELEVANCE_SCORE,
    section_thresholds: dict = None,
):
    """
    Relevance is now judged solely on experience and project chunks -- the
    only sections that should adapt to a target mission. Static sections
    (skills, education, summary, etc.) no longer participate in the
    relevance decision, only in the final matched CV JSON output.
    """
    if section_thresholds is None:
        section_thresholds = PASS_A_SECTION_THRESHOLDS

    sections_to_check = ["experience", "project"]

    best_scores = []
    for section in sections_to_check:
        threshold = section_thresholds.get(section, 0.8)
        res = store.search_section(
            query_vec, chunk_types=section, candidate_id=candidate_id,
            distance_threshold=threshold,
            min_results=0, max_results=3,
        )
        if res:
            best_scores.append(max(distance_to_score(r["distance"]) for r in res))

    if not best_scores:
        return False, 0.0

    sections_above = sum(1 for s in best_scores if s >= min_score)
    avg_score = sum(best_scores) / len(best_scores)
    return sections_above >= 1 and avg_score >= (min_score * 0.5), avg_score


# Search configuration per section chunk_type, calibrated empirically.
SEARCH_CONFIG = {
    "summary": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "functional_skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "expertise_areas": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "experience": {"distance_threshold": 0.35, "min_results": 0, "max_results": 1},
    "project": {"distance_threshold": 0.5, "min_results": 0, "max_results": 1},

    # OPTIONNELLES : min_results=0
    "education": {"distance_threshold": 0.7, "min_results": 0, "max_results": 1},
    "languages": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "certifications": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "countries_worked": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "professional_affiliations": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
}

# experience et project cherchés SEPAREMENT (pas de liste fusionnée), chacun
# avec son propre threshold calibré. min_results/max_results restent communs
# pour l'instant (pas de signal du grid search pour les différencier).
EXPERIENCE_SEARCH_CONFIG = {"distance_threshold": 0.35, "min_results": 0, "max_results": 6}
PROJECT_SEARCH_CONFIG = {"distance_threshold": 0.5, "min_results": 0, "max_results": 6}

# chunk_types resolved via exact index (no text-matching needed)
INDEXED_TYPES = {"experience", "project"}

# chunk_types resolved via text-overlap against a list of Mongo items
LIST_TYPES = {"expertise_areas", "functional_skills", "education", "languages", "certifications"}


def build_matched_cv_json(store, mongo_collection, candidate_id: str, query_vec: list[float]) -> dict:
    """
    Static sections (summary, skills, education, etc.) are included wholesale
    from Mongo — no semantic filtering. Only experience/project go through
    Chroma search, since that's the only part of a CV that should adapt to
    the target mission.

    mongo_collection is expected to be scoped to merged_candidates — each
    candidate has a single consolidated document (no versions, no version
    dedup needed here: that's already resolved upstream at merge time).

    NOTE: no relevance gate here on purpose. This function is called both for
    single-CV-upload flows (user wants a JSON regardless of match quality) and
    for batch scans across the whole candidate base (where the caller applies
    is_candidate_relevant_v2 itself beforehand and skips irrelevant candidates).
    Keeping the gate out of this function keeps both use cases correct without
    a mode flag.
    """
    candidate = mongo_collection.find_one({"candidate_id": ObjectId(candidate_id)})
    if not candidate:
        return {}

    result = {}

    STATIC_SECTIONS = [
        "summary", "skills", "expertise_areas", "functional_skills",
        "education", "languages", "certifications",
        "countries_worked", "professional_affiliations",
    ]
    for section in STATIC_SECTIONS:
        value = candidate.get(section)
        if value:
            result[section] = value

    # experience + project : recherches séparées, thresholds différents
    experience_res = store.search_section(
        query_vec, chunk_types="experience", candidate_id=candidate_id,
        **EXPERIENCE_SEARCH_CONFIG
    )
    project_res = store.search_section(
        query_vec, chunk_types="project", candidate_id=candidate_id,
        **PROJECT_SEARCH_CONFIG
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

    if experiences:
        result["experience"] = experiences
    if projects:
        result["projects"] = projects

    return result