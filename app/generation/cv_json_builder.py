from app.generation.mongo_resolver import (
    resolve_chunk_to_mongo_source,
    resolve_list_section_matches,
)



MIN_RELEVANCE_SCORE = 40.0  # en %, seuil minimal pour considérer un candidat pertinent pour la mission


def distance_to_score(distance: float) -> float:
    """Convert a cosine distance into a 0-100% similarity score."""
    similarity = 1 - distance
    return round(max(0, similarity) * 100, 1)


def is_candidate_relevant(
    store,
    candidate_id: str,
    version_number: int,
    query_vec: list[float],
    min_score: float = 35.0,
    min_critical_sections: int = 1,
) -> bool:
    """
    Garde-fou Passe A : vérifie si le candidat est globalement pertinent pour la mission.
    
    Corrections par rapport à l'ancienne version :
    - Appels search_section SEPARES par chunk_type (pas de liste mélangée qui brouille les scores)
    - Utilise le MAX par section critique, pas la MOYENNE globale
    - Un candidat hors-sujet avec des micro-matchs partout ne passera plus le filtre
    """
    critical_sections = ["summary", "skills", "expertise_areas", "experience","projet"]
    
    best_scores = []
    has_any_result = False
    
    for section in critical_sections:
        # BUG CORRIGE : un seul chunk_type par appel
        res = store.search_section(
            query_vec,
            chunk_types=section,
            candidate_id=candidate_id,
            version_number=version_number,
            distance_threshold=2.0,   # large : on laisse le score décider après
            min_results=1,
            max_results=3,
        )
        
        if res:
            has_any_result = True
            best_score = max(distance_to_score(r["distance"]) for r in res)
            best_scores.append(best_score)
        else:
            best_scores.append(0.0)
    
    if not has_any_result:
        return False
    
    # CRITERE 1 (principal) : au moins N sections critiques dépassent le seuil
    # Un vrai match a typiquement summary ET skills qui matchent fort
    sections_above_threshold = sum(1 for s in best_scores if s >= min_score)
    if sections_above_threshold >= min_critical_sections:
        return True
    
    # CRITERE 2 (fallback conservateur) : moyenne très élevée sur les sections critiques
    # Pour les profils transverses qui matchent partout un peu (ex: consultant senior généraliste)
    avg_score = sum(best_scores) / len(best_scores)
    return avg_score >= (min_score + 15)   # seuil plus strict : 50 si min_score=35

def build_matched_cv_json(store, mongo_collection, candidate_id: str, version_number: int, query_vec: list[float]) -> dict:
    """
    Orchestrate the full retrieval + resolution pipeline for one candidate.
    Returns an empty dict if the candidate is not relevant enough for this mission (Pass A gate).
    """
    if not is_candidate_relevant(store, candidate_id, version_number, query_vec):
        return {}

    result = {}




# Search configuration per section chunk_type, calibrated empirically.
# Sections that resolve via exact index (experience/project) or plain
# value (summary, skills, countries_worked, professional_affiliations)
# vs. sections that resolve via text-overlap matching (the LIST_TYPE ones)
# are all searched the same way — only the resolution step differs.
# Dans app/generation/cv_json_builder.py
SEARCH_CONFIG = {
    "summary": {"distance_threshold": 0.5, "min_results": 1, "max_results": 1},
    "skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "functional_skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "expertise_areas": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "experience": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "project": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    
    # OPTIONNELLES : min_results=0
    "education": {"distance_threshold": 0.7, "min_results": 0, "max_results": 1},
    "languages": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "certifications": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "countries_worked": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "professional_affiliations": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
}

# experience/project handled separately: searched together, multiple results expected
WORK_SEARCH_CONFIG = {"distance_threshold": 0.6, "min_results": 2, "max_results": 6}

# chunk_types resolved via exact index (no text-matching needed)
INDEXED_TYPES = {"experience", "project"}

# chunk_types resolved via text-overlap against a list of Mongo items
LIST_TYPES = {"expertise_areas", "functional_skills", "education", "languages", "certifications"}


def build_matched_cv_json(store, mongo_collection, candidate_id: str, version_number: int, query_vec: list[float]) -> dict:
    """
    Orchestrate the full retrieval + resolution pipeline for one candidate:
    - search each section type in Chroma with its calibrated parameters
    - resolve matched chunks back to their exact Mongo source data
    - assemble a clean structured JSON, ready for CV template rendering

    No LLM involved: Chroma decides relevance, Mongo provides the exact data.
    """
    result = {}

    # 1. simple/list sections
    for chunk_type, params in SEARCH_CONFIG.items():
        res = store.search_section(
            query_vec, chunk_types=chunk_type, candidate_id=candidate_id,version_number=version_number, **params
        )
        if not res:
            continue

        if chunk_type in LIST_TYPES:
            # merge matched items across all returned chunks for this type, deduplicated by content
            all_items = []
            seen = set()
            for r in res:
                items = resolve_list_section_matches(mongo_collection, r["metadata"], r["text"])
                for item in items:
                    key = str(item)  # simple dedup key
                    if key not in seen:
                        seen.add(key)
                        all_items.append(item)
            if all_items:
                result[chunk_type] = all_items
        else:
            # simple value sections (summary, skills, countries_worked, professional_affiliations)
            value = resolve_chunk_to_mongo_source(mongo_collection, res[0]["metadata"])
            if value:
                result[chunk_type] = value

    # 2. experience + project, searched together, resolved by exact index
    work_res = store.search_section(
        query_vec, chunk_types=["experience", "project"], candidate_id=candidate_id,version_number=version_number, **WORK_SEARCH_CONFIG
    )

    experiences = []
    projects = []
    seen_experience_indices = set()
    seen_project_indices = set()

    for r in work_res:
        metadata = r["metadata"]
        chunk_type = metadata["chunk_type"]

        if chunk_type == "experience":
            idx = metadata["experience_index"]
            if idx in seen_experience_indices:
                continue
            seen_experience_indices.add(idx)
            item = resolve_chunk_to_mongo_source(mongo_collection, metadata)
            if item:
                experiences.append(item)

        elif chunk_type == "project":
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