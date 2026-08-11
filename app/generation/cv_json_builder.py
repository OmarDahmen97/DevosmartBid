# file: app/generation/cv_json_builder.py

from app.embedding.embedding_chunker import serialize_experience_to_text
from app.generation.mongo_resolver import (
    resolve_chunk_to_mongo_source,
    resolve_list_section_matches,
)
from app.generation.experience_adapter import (
    adapt_selected_experiences,
    adapt_selected_projects,
)

from rapidfuzz import fuzz
from bson import ObjectId


from app.config import (
    AUTO_SELECT_EXPERIENCE_THRESHOLD,
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


SEARCH_CONFIG = {
    "summary": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "functional_skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "expertise_areas": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "experience": {"distance_threshold": 0.35, "min_results": 0, "max_results": 1},
    "project": {"distance_threshold": 0.5, "min_results": 0, "max_results": 1},
    "education": {"distance_threshold": 0.7, "min_results": 0, "max_results": 1},
    "languages": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "certifications": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "countries_worked": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "professional_affiliations": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
}

EXPERIENCE_SEARCH_CONFIG = {"distance_threshold": 0.35, "min_results": 1, "max_results": 6}
PROJECT_SEARCH_CONFIG = {"distance_threshold": 0.5, "min_results": 1, "max_results": 6}

INDEXED_TYPES = {"experience", "project"}
LIST_TYPES = {"expertise_areas", "functional_skills", "education", "languages", "certifications"}


def _dedupe_ranked_by_index(raw_results: list[dict], index_field: str) -> list[dict]:
    best_by_index: dict[int, dict] = {}
    for r in raw_results:
        idx = r["metadata"][index_field]
        if idx not in best_by_index or r["distance"] < best_by_index[idx]["distance"]:
            best_by_index[idx] = r
    return sorted(best_by_index.values(), key=lambda r: r["distance"])


def get_ranked_experiences(
    store, mongo_collection, candidate_id: str, query_vec: list[float],
auto_select_threshold: float = AUTO_SELECT_EXPERIENCE_THRESHOLD,
) -> list[dict]:
    if auto_select_threshold is None:
        auto_select_threshold = EXPERIENCE_SEARCH_CONFIG["distance_threshold"]

    raw = store.get_ranked_chunks(query_vec, chunk_type="experience", candidate_id=candidate_id)
    ranked = _dedupe_ranked_by_index(raw, "experience_index")

    output = []
    for r in ranked:
        item = resolve_chunk_to_mongo_source(mongo_collection, r["metadata"])
        if not item:
            continue
        output.append({
            "experience_index": r["metadata"]["experience_index"],
            "item": item,
            "score": distance_to_score(r["distance"]),
            "auto_selected": r["distance"] <= auto_select_threshold,
        })
    return output


def get_ranked_projects(
    store, mongo_collection, candidate_id: str, query_vec: list[float],
    auto_select_threshold: float = None,
) -> list[dict]:
    if auto_select_threshold is None:
        auto_select_threshold = PROJECT_SEARCH_CONFIG["distance_threshold"]

    raw = store.get_ranked_chunks(query_vec, chunk_type="project", candidate_id=candidate_id)
    ranked = _dedupe_ranked_by_index(raw, "project_index")

    output = []
    for r in ranked:
        item = resolve_chunk_to_mongo_source(mongo_collection, r["metadata"])
        if not item:
            continue
        output.append({
            "project_index": r["metadata"]["project_index"],
            "item": item,
            "score": distance_to_score(r["distance"]),
            "auto_selected": r["distance"] <= auto_select_threshold,
        })
    return output


def build_matched_cv_json(
    store,
    mongo_collection,
    candidate_id: str,
    query_vec: list[float],
    mission_text: str = None,
    target_language: str = "English",
) -> dict:
    """
    Constructs the target CV JSON by searching Chroma for experiences/projects
    and fetching static sections from MongoDB.

    If `mission_text` is provided, selected experiences and projects are
    dynamically adapted to the mission's vocabulary using Gemini before constructing
    the final JSON response.
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

    # 1. Selection via recherche vectorielle
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
            # On conserve explicitement l'index pour permettre l'adaptation
            item["experience_index"] = idx
            experiences.append(item)

    for r in project_res:
        metadata = r["metadata"]
        idx = metadata["project_index"]
        if idx in seen_project_indices:
            continue
        seen_project_indices.add(idx)
        item = resolve_chunk_to_mongo_source(mongo_collection, metadata)
        if item:
            # On conserve explicitement l'index pour permettre l'adaptation
            item["project_index"] = idx
            projects.append(item)

    # 2. Adaptation dynamique avec le LLM si un texte de mission est fourni
    if mission_text:
        if experiences:
            adapted_exp_map = adapt_selected_experiences(
                experiences, mission_text, target_language
            )
            for exp in experiences:
                idx = exp["experience_index"]
                if idx in adapted_exp_map:
                    if adapted_exp_map[idx].get("description"):
                        exp["description"] = adapted_exp_map[idx]["description"]
                    if adapted_exp_map[idx].get("responsibilities"):
                        exp["responsibilities"] = adapted_exp_map[idx]["responsibilities"]

        if projects:
            adapted_proj_map = adapt_selected_projects(
                projects, mission_text, target_language
            )
            for proj in projects:
                idx = proj["project_index"]
                if idx in adapted_proj_map and adapted_proj_map[idx].get("description"):
                    proj["description"] = adapted_proj_map[idx]["description"]

    # 3. Assemblage du résultat final
    if experiences:
        result["experience"] = experiences
    if projects:
        result["projects"] = projects

    return result